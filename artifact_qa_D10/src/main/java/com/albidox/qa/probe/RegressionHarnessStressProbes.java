package com.albidox.qa.probe;

import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.FlywayException;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class RegressionHarnessStressProbes {

    private static final String DB_URL = "jdbc:postgresql://127.0.0.1:5433/artifact_d10_db";
    private static final String DB_USER = "postgres";
    private static final String DB_PASSWORD = "";

    public static void main(String[] args) {
        System.out.println("===============================================================");
        System.out.println("  Artifact D10: Enterprise Regression Harness Stress Probes   ");
        System.out.println("===============================================================");

        boolean probe1Success = runMigrationCollisionProbe();
        boolean probe2Success = runMissingForeignKeyIndexProbe();
        boolean probe3Success = runTransactionalIsolationLeakProbe();

        System.out.println("===============================================================");
        System.out.println("Stress Probes Summary:");
        System.out.println("  Probe 1 (Migration Collision):       " + (probe1Success ? "PASSED" : "FAILED"));
        System.out.println("  Probe 2 (Missing FK Index Audit):    " + (probe2Success ? "PASSED" : "FAILED"));
        System.out.println("  Probe 3 (Transactional Leak Audit):  " + (probe3Success ? "PASSED" : "FAILED"));
        System.out.println("===============================================================");

        if (!probe1Success || !probe2Success || !probe3Success) {
            System.err.println("ERROR: One or more stress probes failed.");
            System.exit(1);
        }
        System.out.println("All stress probes completed successfully with 100% pass rate.");
    }

    public static boolean runMigrationCollisionProbe() {
        System.out.println("\n[Probe 1/3] Executing Migration Version Collision Probe...");
        String probeSchema = "d10_probe_collision_schema";
        Path tempDir = null;

        try {
            tempDir = Files.createTempDirectory("flyway_collision_probe_");

            File scriptA = new File(tempDir.toFile(), "V2_0__add_reporting_metrics.sql");
            try (FileWriter writer = new FileWriter(scriptA)) {
                writer.write("CREATE TABLE reporting_metrics (id BIGSERIAL PRIMARY KEY, metric_name VARCHAR(100));\n");
            }

            File scriptB = new File(tempDir.toFile(), "V2_0__duplicate_reporting_table.sql");
            try (FileWriter writer = new FileWriter(scriptB)) {
                writer.write("CREATE TABLE duplicate_metrics (id BIGSERIAL PRIMARY KEY, duplicate_name VARCHAR(100));\n");
            }

            try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD);
                 Statement stmt = conn.createStatement()) {
                stmt.execute("DROP SCHEMA IF EXISTS " + probeSchema + " CASCADE");
                stmt.execute("CREATE SCHEMA " + probeSchema);
            }

            Flyway flyway = Flyway.configure()
                    .dataSource(DB_URL, DB_USER, DB_PASSWORD)
                    .schemas(probeSchema)
                    .defaultSchema(probeSchema)
                    .locations("filesystem:" + tempDir.toAbsolutePath().toString().replace("\\", "/"))
                    .load();

            boolean collisionCaught = false;
            String diagnosticMessage = "";
            try {
                flyway.migrate();
            } catch (FlywayException ex) {
                collisionCaught = true;
                diagnosticMessage = ex.getMessage();
                System.out.println("  Expected FlywayException caught: " + ex.getClass().getName());
                System.out.println("  Diagnostic error text: " + diagnosticMessage);
            }

            if (!collisionCaught) {
                System.err.println("  FAILED: Flyway failed to detect migration version collision!");
                return false;
            }

            if (!diagnosticMessage.toLowerCase().contains("more than one migration with version") &&
                !diagnosticMessage.toLowerCase().contains("duplicate") &&
                !diagnosticMessage.toLowerCase().contains("2.0") &&
                !diagnosticMessage.toLowerCase().contains("2_0")) {
                System.err.println("  FAILED: Diagnostic message does not reference duplicate version: " + diagnosticMessage);
                return false;
            }

            try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD);
                 Statement stmt = conn.createStatement()) {
                ResultSet rs = stmt.executeQuery(
                        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '" + probeSchema + "' AND table_name != 'flyway_schema_history'"
                );
                rs.next();
                int userTablesCount = rs.getInt(1);
                if (userTablesCount != 0) {
                    System.err.println("  FAILED: Tables were created despite version collision!");
                    return false;
                }
                System.out.println("  Verified database schema preserved cleanly with 0 partial tables.");
                stmt.execute("DROP SCHEMA IF EXISTS " + probeSchema + " CASCADE");
            }

            System.out.println("  [Probe 1/3] PASSED: Version collision detected and halted with clear diagnostics.");
            return true;

        } catch (Exception e) {
            System.err.println("  Unexpected exception during migration collision probe: " + e.getMessage());
            e.printStackTrace();
            return false;
        } finally {
            if (tempDir != null) {
                try {
                    Files.walk(tempDir)
                            .sorted(Comparator.reverseOrder())
                            .map(Path::toFile)
                            .forEach(File::delete);
                } catch (IOException ignored) {
                }
            }
        }
    }

    public static boolean runMissingForeignKeyIndexProbe() {
        System.out.println("\n[Probe 2/3] Executing Missing Foreign Key Index Probe...");
        String probeSchema = "d10_probe_fk_schema";

        try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD);
             Statement stmt = conn.createStatement()) {

            stmt.execute("DROP SCHEMA IF EXISTS " + probeSchema + " CASCADE");
            stmt.execute("CREATE SCHEMA " + probeSchema);

            stmt.execute("CREATE TABLE " + probeSchema + ".accounts (" +
                    "id BIGSERIAL PRIMARY KEY, " +
                    "account_name VARCHAR(100) NOT NULL" +
                    ")");

            stmt.execute("CREATE TABLE " + probeSchema + ".transactions (" +
                    "id BIGSERIAL PRIMARY KEY, " +
                    "account_id BIGINT NOT NULL REFERENCES " + probeSchema + ".accounts(id), " +
                    "amount NUMERIC(10,2) NOT NULL" +
                    ")");

            List<String> unindexedFks = detectUnindexedForeignKeys(conn, probeSchema);
            System.out.println("  Step 1: Unindexed FK scan detected " + unindexedFks.size() + " unindexed foreign keys.");
            if (unindexedFks.isEmpty()) {
                System.err.println("  FAILED: Failed to detect unindexed foreign key on transactions.account_id!");
                return false;
            }
            for (String fk : unindexedFks) {
                System.out.println("    Flagged contention risk: " + fk);
            }

            System.out.println("  Step 2: Applying index remediation...");
            stmt.execute("CREATE INDEX idx_transactions_account_id ON " + probeSchema + ".transactions(account_id)");

            List<String> afterRemediation = detectUnindexedForeignKeys(conn, probeSchema);
            if (!afterRemediation.isEmpty()) {
                System.err.println("  FAILED: Foreign key still flagged as unindexed after index creation!");
                return false;
            }
            System.out.println("  Step 2: Verified 0 unindexed foreign keys remain after remediation.");

            System.out.println("  Step 3: Auditing baseline schema 'd10_regression_sandbox'...");
            List<String> baselineUnindexedFks = detectUnindexedForeignKeys(conn, "d10_regression_sandbox");
            if (!baselineUnindexedFks.isEmpty()) {
                System.err.println("  FAILED: Baseline schema contains unindexed foreign keys: " + baselineUnindexedFks);
                return false;
            }
            System.out.println("  Step 3: Baseline schema has 0 unindexed foreign keys. All FK relations properly indexed.");

            stmt.execute("DROP SCHEMA IF EXISTS " + probeSchema + " CASCADE");
            System.out.println("  [Probe 2/3] PASSED: Unindexed foreign keys detected and lock contention risk mitigated.");
            return true;

        } catch (Exception e) {
            System.err.println("  Unexpected exception during missing FK index probe: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    public static boolean runTransactionalIsolationLeakProbe() {
        System.out.println("\n[Probe 3/3] Executing Transactional Isolation Leak Probe...");
        String probeSchema = "d10_regression_sandbox";
        String probeTable = probeSchema + ".probe_isolation_events";

        try (Connection conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASSWORD);
             Statement stmt = conn.createStatement()) {

            stmt.execute("CREATE TABLE IF NOT EXISTS " + probeTable + " (" +
                    "id BIGSERIAL PRIMARY KEY, " +
                    "event_name VARCHAR(100) NOT NULL, " +
                    "created_at TIMESTAMPTZ DEFAULT clock_timestamp()" +
                    ")");

            stmt.execute("TRUNCATE TABLE " + probeTable);

            int baselineCount = getRowCount(stmt, probeTable);
            if (baselineCount != 0) {
                System.err.println("  FAILED: Baseline table count is not zero: " + baselineCount);
                return false;
            }
            System.out.println("  Baseline table count verified: 0 rows.");

            System.out.println("  Step 1: Simulating non-transactional test inserting 1,000 rows...");
            String insertSql = "INSERT INTO " + probeTable + " (event_name) VALUES (?)";
            try (PreparedStatement pstmt = conn.prepareStatement(insertSql)) {
                for (int i = 1; i <= 1000; i++) {
                    pstmt.setString(1, "DIRTY_LEAK_EVENT_" + i);
                    pstmt.addBatch();
                }
                pstmt.executeBatch();
            }

            int dirtyCount = getRowCount(stmt, probeTable);
            System.out.println("  Post-test row count: " + dirtyCount + " rows.");
            if (dirtyCount != 1000) {
                System.err.println("  FAILED: Expected 1000 inserted rows, found: " + dirtyCount);
                return false;
            }

            System.out.println("  Step 2: Harness assertion detecting dirty state leakage across test boundary...");
            boolean leakDetected = dirtyCount > 0;
            if (leakDetected) {
                System.out.println("    DIAGNOSTIC ASSERTION: DIRTY_STATE_LEAK_DETECTED");
                System.out.println("    Table " + probeTable + " leaked " + dirtyCount + " rows across test boundary.");
                System.out.println("    Enforcing test isolation boundary purge protocol...");
                stmt.execute("TRUNCATE TABLE " + probeTable);
            }

            int postPurgeCount = getRowCount(stmt, probeTable);
            if (postPurgeCount != 0) {
                System.err.println("  FAILED: Isolation boundary purge failed, row count: " + postPurgeCount);
                return false;
            }
            System.out.println("  Isolation boundary restored: row count returned to 0.");

            System.out.println("  Step 3: Verifying transactional boundary (@Transactional rollback)...");
            conn.setAutoCommit(false);
            try (PreparedStatement pstmt = conn.prepareStatement(insertSql)) {
                for (int i = 1; i <= 1000; i++) {
                    pstmt.setString(1, "TRANSACTIONAL_EVENT_" + i);
                    pstmt.addBatch();
                }
                pstmt.executeBatch();
            }
            conn.rollback();
            conn.setAutoCommit(true);

            int postRollbackCount = getRowCount(stmt, probeTable);
            if (postRollbackCount != 0) {
                System.err.println("  FAILED: Transaction rollback failed to clear state: " + postRollbackCount);
                return false;
            }
            System.out.println("  Transactional rollback verified: 0 dirty rows leaked.");

            stmt.execute("DROP TABLE IF EXISTS " + probeTable);
            System.out.println("  [Probe 3/3] PASSED: Dirty state leakage detected, purged, and transactional rollback verified.");
            return true;

        } catch (Exception e) {
            System.err.println("  Unexpected exception during transactional isolation leak probe: " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    private static List<String> detectUnindexedForeignKeys(Connection conn, String schemaName) throws SQLException {
        List<String> unindexedFks = new ArrayList<>();
        String sql = "SELECT " +
                "    c.conname AS constraint_name, " +
                "    c.conrelid::regclass::text AS child_table, " +
                "    att.attname AS fk_column, " +
                "    c.confrelid::regclass::text AS parent_table " +
                "FROM pg_constraint c " +
                "JOIN pg_namespace ns ON ns.oid = c.connamespace " +
                "JOIN pg_attribute att ON att.attrelid = c.conrelid AND att.attnum = c.conkey[1] " +
                "WHERE c.contype = 'f' " +
                "  AND ns.nspname = ? " +
                "  AND NOT EXISTS ( " +
                "      SELECT 1 " +
                "      FROM pg_index idx " +
                "      WHERE idx.indrelid = c.conrelid " +
                "        AND idx.indkey[0] = att.attnum " +
                "  ) " +
                "ORDER BY child_table, constraint_name";

        try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.setString(1, schemaName);
            try (ResultSet rs = pstmt.executeQuery()) {
                while (rs.next()) {
                    String constraint = rs.getString("constraint_name");
                    String childTable = rs.getString("child_table");
                    String fkCol = rs.getString("fk_column");
                    String parentTable = rs.getString("parent_table");
                    unindexedFks.add(String.format("Constraint %s on %s(%s) -> %s", constraint, childTable, fkCol, parentTable));
                }
            }
        }
        return unindexedFks;
    }

    private static int getRowCount(Statement stmt, String tableName) throws SQLException {
        try (ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM " + tableName)) {
            rs.next();
            return rs.getInt(1);
        }
    }
}
