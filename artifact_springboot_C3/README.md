# Artifact C3-R1: Enterprise OpenRewrite Java AST Modernization Build

## Executive Summary
This artifact demonstrates an enterprise-grade automated code modernization pipeline migrating legacy Java EE / Spring Boot 2.x codebases (`javax.*` namespace) to Jakarta EE 10 / Spring Boot 3.4.1 on Java 21 LTS using **OpenRewrite Lossless Semantic Tree (LST)** refactoring recipes.

Manual find-and-replace corrupts JDK standard packages like `javax.sql.DataSource`. OpenRewrite performs type-aware AST refactoring with zero manual edits, preserving JDK namespaces and code formatting.

## Verified Benchmark Metrics
- **Classes Modernized:** 5 enterprise entities (`Customer`, `Product`, `OrderEntity`, `Invoice`, `AuditLog`)
- **Statements Transformed:** 44 import statements & annotation bindings
- **JDK Namespace Preservation:** 100% (`javax.sql.DataSource` preserved intact)
- **OpenRewrite AST Execution Time:** ~34.0 seconds (automated refactoring of entire codebase)
- **Maven Test Suite Execution:** 14.2 seconds
- **JUnit 5 / Surefire Test Pass Rate:** 100% (1/1 suites, 5 entities persisted to in-memory H2 database)
- **Syntax / Formatting Corruptions:** 0
- **Manual Edits Required:** 0

---

## Reproduction & Verification Steps

### 1. Verify Legacy Build Failure
Run compilation against the legacy `javax.*` classes on Spring Boot 3.4.1 / Java 21:
```bash
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" compile
```
**Outcome:** Compilation fails with 100 compiler errors (`package javax.persistence does not exist`, `package javax.validation.constraints does not exist`, `package javax.annotation does not exist`). Output captured in `output/before/compile_error.txt`.

### 2. Execute Automated AST Transformation
Run OpenRewrite recipe via `rewrite-maven-plugin`:
```bash
set MAVEN_OPTS="-Xmx2048m -XX:+UseG1GC"
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" rewrite:run -Dmaven.compiler.failOnError=false
```
**Outcome:** OpenRewrite applies `org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta`. All 5 source files are rewritten cleanly in place.

### 3. Verify Test Suite & Database Persistence
Run full clean build and JUnit 5 test suite:
```bash
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" clean test
```
**Outcome:** 100% GREEN build. Schema generated on H2, entities persisted and queried successfully. Logs captured in `output/after/surefire_report.txt`.

---

## Deliverables & Artifact Manifest
- `pom.xml`: Spring Boot 3.4.1 parent POM with configured `rewrite-maven-plugin` and recipe dependencies.
- `rewrite.yml`: Declarative OpenRewrite recipe configuration.
- `fix.patch` & `output/fix.patch`: Unified diff showing exact lossless transformations across all 5 model files.
- `before/compile_error.txt` & `output/before/compile_error.txt`: Baseline compilation failure logs proving legacy breakdown.
- `before/CustomerLegacy.java`: Preserved reference legacy model showing `javax.*` annotations and `javax.sql.DataSource`.
- `output/after/import_diff.txt`: Transformed statements audit log.
- `output/after/surefire_report.txt`: Maven Surefire test execution report showing 100% green tests.
- `benchmark_summary.md`: Side-by-side benchmark comparing manual refactoring vs OpenRewrite AST modernization.
- `OPENREWRITE_MIGRATION_REPORT.md`: Comprehensive executive client migration report and runbook.
- `enterprise_ast_migration_runbook.md` & `output/enterprise_ast_migration_runbook.md`: Production runbook for enterprise multi-module Maven monorepo AST migrations, JDK namespace matrix, and unmigrated third-party handling.

---

## Author
**Sk Ashfaq Bux**  
*Lead Software Engineering Specialist*  
GitHub: [github.com/Albidox](https://github.com/Albidox)
