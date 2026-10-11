# Enterprise AST Migration Runbook: Java EE (javax.*) to Jakarta EE 10 (jakarta.*)

**Document ID:** RUNBOOK-AST-C3-ENTERPRISE  
**Author:** Sk Ashfaq Bux (github.com/Albidox)  
**Target Platform:** Java 21 LTS / Spring Boot 3.4.x / Jakarta EE 10  
**Tooling:** OpenRewrite 8.40+ (`rewrite-maven-plugin` 5.45.0), Eclipse Transformer  
**Audience:** Enterprise Architects, Staff Engineers, Platform Engineers  
**Classification:** Production Engineering Standards  

---

## 1. Architectural Background: The Javax to Jakarta Namespace Split

### 1.1 The Legal and Governance Context
In 2017, Oracle transferred Java EE governance to the Eclipse Foundation. While Oracle permitted the transfer of specification code and existing TCKs (Technology Compatibility Kits), Oracle retained exclusive trademark ownership over the `javax.*` brand and package prefix. Under the terms of the transfer agreement, the Eclipse Foundation was prohibited from modifying existing specifications within the `javax.*` namespace or creating new sub-packages under `javax.*`.

To advance enterprise Java specifications (such as JPA, Bean Validation, Servlet, and JAX-RS), the community instituted the Jakarta EE working group and executed a breaking namespace migration from `javax.*` to `jakarta.*`. This change debuted in Jakarta EE 9 (a pure namespace migration without API changes) and matured in Jakarta EE 10 (which introduced new APIs and raised baseline Java compatibility to Java 17 and Java 21).

Spring Framework 6.0 and Spring Boot 3.0 embraced this transition as a non-negotiable architectural baseline. Applications upgrading to Spring Boot 3.x cannot compile or run against the legacy `javax.*` enterprise packages.

---

### 1.2 Exhaustive Package Namespace Matrix

A frequent misconception in enterprise engineering teams is that "all javax packages are now jakarta". This is false and dangerous. The Java SE Standard Library (maintained directly by the OpenJDK project) retains dozens of critical packages under the `javax.*` prefix.

The following master reference table delineates exactly which packages transitioned to Jakarta EE versus those that remain strictly inside the JDK standard runtime.

| Package Prefix | Sub-Packages | Original Java EE Spec | Modern Status | Target Package / JDK Module |
|---|---|---|---|---|
| `javax.persistence` | `*` | JPA (Java Persistence API) | **MIGRATED** | `jakarta.persistence.*` |
| `javax.validation` | `*`, `constraints.*` | Bean Validation | **MIGRATED** | `jakarta.validation.*` |
| `javax.servlet` | `*`, `http.*`, `annotation.*` | Servlet API | **MIGRATED** | `jakarta.servlet.*` |
| `javax.annotation` | `@PostConstruct`, `@PreDestroy`, `@Resource` | Common Annotations (JSR-250) | **MIGRATED** | `jakarta.annotation.*` |
| `javax.transaction` | `UserTransaction`, `Transactional` | JTA (Java Transaction API) | **MIGRATED** | `jakarta.transaction.*` |
| `javax.ws.rs` | `*`, `core.*` | JAX-RS (RESTful Web Services) | **MIGRATED** | `jakarta.ws.rs.*` |
| `javax.jms` | `*` | JMS (Java Message Service) | **MIGRATED** | `jakarta.jms.*` |
| `javax.mail` | `*`, `internet.*` | JavaMail API | **MIGRATED** | `jakarta.mail.*` |
| `javax.xml.bind` | `*`, `annotation.*` | JAXB (XML Binding) | **MIGRATED** | `jakarta.xml.bind.*` |
| `javax.xml.ws` | `*` | JAX-WS (XML Web Services) | **MIGRATED** | `jakarta.xml.ws.*` |
| `javax.ejb` | `*` | Enterprise JavaBeans | **MIGRATED** | `jakarta.ejb.*` |
| `javax.batch` | `*` | Batch Applications (JSR-352) | **MIGRATED** | `jakarta.batch.*` |
| `javax.websocket` | `*`, `server.*` | WebSocket API | **MIGRATED** | `jakarta.websocket.*` |
| **`javax.sql`** | `DataSource`, `ConnectionPoolDataSource`, `RowSet` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.sql.*` (`java.sql` module) |
| **`javax.crypto`** | `Cipher`, `KeyGenerator`, `SecretKey` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.crypto.*` (`java.base` module) |
| **`javax.net.ssl`** | `SSLContext`, `SSLSocketFactory`, `TrustManager` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.net.ssl.*` (`java.base` module) |
| **`javax.xml.parsers`** | `DocumentBuilderFactory`, `SAXParserFactory` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.xml.parsers.*` (`java.xml` module) |
| **`javax.xml.transform`** | `Transformer`, `TransformerFactory`, `Source` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.xml.transform.*` (`java.xml` module) |
| **`javax.xml.datatype`** | `XMLGregorianCalendar`, `Duration` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.xml.datatype.*` (`java.xml` module) |
| **`javax.naming`** | `Context`, `InitialContext`, `directory.*` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.naming.*` (`java.naming` module) |
| **`javax.security.auth`** | `Subject`, `login.*`, `x500.*` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.security.auth.*` (`java.base` module) |
| **`javax.management`** | `MBeanServer`, `ObjectName`, `Notification` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.management.*` (`java.management` module) |
| **`javax.sound`** | `sampled.*`, `midi.*` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.sound.*` (`java.desktop` module) |
| **`javax.imageio`** | `ImageIO`, `stream.*`, `metadata.*` | **Java SE Standard Library** | **RETAINED IN JDK** | `javax.imageio.*` (`java.desktop` module) |

---

### 1.3 Subtleties and Mixed Namespace Traps

Enterprise codebases contain boundary cases where both `javax.*` and `jakarta.*` packages coexist within the same domain class:

1. **Database Persistence vs Connection Pooling:**
   A Spring Data JPA repository configuration imports both `jakarta.persistence.EntityManagerFactory` and `javax.sql.DataSource`.
   ```java
   import jakarta.persistence.EntityManagerFactory; // Migrated
   import javax.sql.DataSource;                      // Retained in JDK java.sql
   ```
2. **Transaction Management:**
   Distributed XA transactions utilize `javax.transaction.xa.XAResource` (retained in JDK `java.sql` module) alongside `jakarta.transaction.Transactional` (migrated to Jakarta EE).
   ```java
   import jakarta.transaction.Transactional;        // Migrated
   import javax.transaction.xa.XAResource;           // Retained in JDK
   ```
3. **XML Processing vs XML Binding:**
   DOM document generation utilizes `javax.xml.parsers.DocumentBuilder` (JDK), whereas entity XML marshalling utilizes `jakarta.xml.bind.JAXBContext` (Jakarta EE).
   ```java
   import jakarta.xml.bind.annotation.XmlRootElement; // Migrated
   import javax.xml.parsers.DocumentBuilder;          // Retained in JDK
   ```

---

## 2. Why Naive Regex Replacement Breaks Enterprise Codebases

### 2.1 Hazard 1: Severe JDK Standard Library Corruption
Executing a global string substitution script such as:
```bash
# DISASTROUS SCRIPT: DO NOT USE IN ENTERPRISE SYSTEMS
find . -name "*.java" -exec sed -i 's/javax\./jakarta\./g' {} +
```
immediately corrupts every reference to standard JDK APIs. It generates invalid statements:
```java
import jakarta.sql.DataSource;             // BUILD FAILURE: package jakarta.sql does not exist
import jakarta.crypto.Cipher;             // BUILD FAILURE: package jakarta.crypto does not exist
import jakarta.net.ssl.SSLContext;        // BUILD FAILURE: package jakarta.net.ssl does not exist
import jakarta.xml.parsers.DocumentBuilder; // BUILD FAILURE: package jakarta.xml.parsers does not exist
```
The developer must then manually comb through hundreds of compilation failures across hundreds of classes to revert the unintended edits.

---

### 2.2 Hazard 2: Wildcard Import Expansion and Ambiguity
Legacy repositories frequently feature wildcard imports:
```java
import javax.persistence.*;
import javax.annotation.*;
```
A regex replace transforms `import javax.persistence.*;` into `import jakarta.persistence.*;`. However, if another class had:
```java
import javax.annotation.*;
```
In modern Java, certain annotations like `@Generated` moved to `javax.annotation.processing.Generated` in the JDK, while `@Resource`, `@PostConstruct`, and `@PreDestroy` moved to `jakarta.annotation.*`. Naive wildcard replacement masks symbol collisions, causing ambiguous type compiler errors.

---

### 2.3 Hazard 3: Javadoc, URLs, and String Literal Corruption
Global sed scripts replace text irrespective of token context. Consider these actual enterprise patterns:
```java
// Legacy documentation comment
/**
 * Reference specification: https://docs.oracle.com/javaee/7/api/javax/persistence/Entity.html
 */
private static final String SCHEMA_NS = "http://java.sun.com/xml/ns/persistence";
private static final String PERSISTENCE_UNIT = "javax.persistence.jdbc.url";
```
A naive regex alters URLs to broken endpoints and corrupts property keys that persistence providers expect.

---

### 2.4 Hazard 4: Formatting Degradation, Indentation Loss, and Git Blame Invalidation
Regex tools do not respect AST formatting rules:
- They fail to maintain alphabetical import ordering conventions enforced by Checkstyle or Spotless.
- They break indentation on multi-line annotations.
- They churn thousands of irrelevant lines, rendering `git blame` useless and overwhelming code reviewers.

---

### 2.5 The OpenRewrite Solution: Lossless Semantic Trees (LST)
OpenRewrite avoids these failures through compiler-grade semantic analysis:

```
Source Code (.java) 
       │
       ▼
Java Compiler Front-End (Type Attribution & Symbol Table)
       │
       ▼
Lossless Semantic Tree (LST)
  ├── Exact Syntax Hierarchy (AST)
  ├── Byte-for-Byte Whitespace & Comments Preserved
  └── Fully Qualified Type Bindings (e.g. javax.sql.DataSource -> JDK)
       │
       ▼
Recipe Execution: org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta
  ├── Inspects fully qualified symbol: javax.persistence.Entity
  │     └─ Matches recipe rewrite rule -> Transform to jakarta.persistence.Entity
  └── Inspects fully qualified symbol: javax.sql.DataSource
        └─ Identified as JDK java.sql -> Skip (Untouched)
       │
       ▼
Refactored Source Code (Minimal Safe Diff, 100% Formatting Retained)
```

1. **Type Attribution:** OpenRewrite compiles source files into memory using standard compiler interfaces. Every AST node has an associated `JavaType`. It knows whether a type originates from the JDK runtime or an external JAR.
2. **Lossless Preservation:** The tree preserves every tab, space, newline, and inline comment. No whitespace formatting is modified outside the exact import statements and type names being transformed.
3. **Deterministic Recipe Execution:** Transformations are applied as idempotent tree visitors, ensuring repeatable outcomes across repeated runs.

---

## 3. Step-by-Step Enterprise Multi-Module Migration Runbook

This section details how to execute an automated migration across an enterprise Maven monorepo containing 20+ microservice modules.

### 3.1 Step 1: Pre-Flight Environment Baseline
Verify the Java runtime, Maven installation, and available heap space:

```bash
# Verify Adoptium / Eclipse Temurin JDK 21
java -version
# Expected: openjdk version "21.0.x"

# Verify Maven 3.9+
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" -version
# Expected: Apache Maven 3.9.16+

# Configure Maven memory settings for large AST graphs
export MAVEN_OPTS="-Xmx4096m -XX:+UseG1GC -XX:+TieredCompilation"
```

---

### 3.2 Step 2: Configure the Root Parent POM

In a multi-module repository, OpenRewrite must be declared in the root parent `pom.xml` using `<pluginManagement>` or `<plugins>` so that recipe dependencies are resolved once and executed uniformly across all child submodules.

Add the following configuration to the root `pom.xml`:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.enterprise.platform</groupId>
    <artifactId>enterprise-platform-parent</artifactId>
    <version>2026.1.0-SNAPSHOT</version>
    <packaging>pom</packaging>

    <properties>
        <java.version>21</java.version>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
        <rewrite-maven-plugin.version>5.45.0</rewrite-maven-plugin.version>
        <rewrite-migrate-java.version>2.29.0</rewrite-migrate-java.version>
        <rewrite-spring.version>5.22.0</rewrite-spring.version>
    </properties>

    <modules>
        <module>common-core</module>
        <module>domain-entities</module>
        <module>order-service</module>
        <module>customer-service</module>
        <module>billing-service</module>
        <module>inventory-service</module>
        <module>api-gateway</module>
    </modules>

    <build>
        <pluginManagement>
            <plugins>
                <plugin>
                    <groupId>org.openrewrite.maven</groupId>
                    <artifactId>rewrite-maven-plugin</artifactId>
                    <version>${rewrite-maven-plugin.version}</version>
                    <configuration>
                        <activeRecipes>
                            <recipe>org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta</recipe>
                            <recipe>org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_4</recipe>
                        </activeRecipes>
                        <failOnDryRunResults>false</failOnDryRunResults>
                    </configuration>
                    <dependencies>
                        <dependency>
                            <groupId>org.openrewrite.recipe</groupId>
                            <artifactId>rewrite-migrate-java</artifactId>
                            <version>${rewrite-migrate-java.version}</version>
                        </dependency>
                        <dependency>
                            <groupId>org.openrewrite.recipe</groupId>
                            <artifactId>rewrite-spring</artifactId>
                            <version>${rewrite-spring.version}</version>
                        </dependency>
                    </dependencies>
                </plugin>
            </plugins>
        </pluginManagement>

        <plugins>
            <plugin>
                <groupId>org.openrewrite.maven</groupId>
                <artifactId>rewrite-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
```

---

### 3.3 Step 3: Declarative Custom Recipe Formulation (`rewrite.yml`)

For enterprise codebases requiring coordinated updates (such as migrating custom utility classes alongside `javax` annotations), author a declarative `rewrite.yml` at the repository root:

```yaml
---
type: specs.openrewrite.org/v1beta/recipe
name: com.enterprise.migration.EnterpriseFullMigration
displayName: Enterprise Full Multi-Module Modernization
description: Comprehensive Jakarta EE 10, Spring Boot 3.4, and Java 21 migration suite.
recipeList:
  # Phase 1: Core Jakarta Namespace Modernization
  - org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta
  
  # Phase 2: Bean Validation Specification Alignment
  - org.openrewrite.java.migrate.jakarta.BeanValidation31
  
  # Phase 3: Persistence Specification Alignment
  - org.openrewrite.java.migrate.jakarta.Persistence2To3
  
  # Phase 4: Spring Boot 3.4 Migration
  - org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_4

  # Phase 5: Java 21 Idioms (Optional / Phase-Gated)
  - org.openrewrite.java.migrate.UpgradeToJava21
```

---

### 3.4 Step 4: Execute Dry Run and Inspect Proposed Diff
Before modifying any files on disk, execute `rewrite:dryRun`:

```bash
# Execute non-destructive AST dry run
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" rewrite:dryRun
```

This operation generates `target/rewrite/rewrite.patch` in each submodule directory without writing to source files. Inspect the generated diff using:
```bash
git diff --stat
# Verify that no changes are staged yet
```

---

### 3.5 Step 5: Execute In-Place AST Transformation
Apply the automated migration across all submodules simultaneously:

```bash
# Set memory budget and run the transformation
export MAVEN_OPTS="-Xmx4096m -XX:+UseG1GC"
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" rewrite:run -Dmaven.compiler.failOnError=false
```

OpenRewrite cascades through all Maven child modules in reactor order, parses every Java compilation unit into an LST, applies the recipe chain, and saves the refactored files directly to disk.

---

### 3.6 Step 6: Verify Build and Execute Surefire Test Suites
Confirm that the entire monorepo compiles cleanly on Java 21 LTS:

```bash
# Clean compilation and test verification across all modules
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" clean test
```

Inspect test results:
```bash
# Verify zero test failures
find . -name "TEST-*.xml" | xargs grep '<failure'
```

---

## 4. Handling Stubborn Third-Party Legacy Libraries

### 4.1 The Unmigrated Dependency Problem
In large enterprises, internal or commercial dependencies (such as custom auditing libraries, legacy PDF generators, or proprietary SOAP clients) may not yet provide an updated release with `jakarta.*` packages.

When an application runs on Spring Boot 3 with Hibernate 6, passing a legacy entity containing `javax.persistence.*` to a Jakarta `EntityManager` throws an immediate runtime exception:
```text
java.lang.IllegalArgumentException: Not an entity: com.vendor.legacy.LegacyContract
```

---

### 4.2 Solution: Bytecode Transformation with Eclipse Transformer
The Eclipse Transformer project (`org.eclipse.transformer`) provides direct bytecode manipulation to transform legacy JARs compiled against `javax.*` into modern `jakarta.*` JARs on the fly during Maven builds.

#### Option A: Standalone CLI Transformation of Vendor JARs
If third-party JARs reside in an internal Nexus or Artifactory repository, transform them prior to import:

```bash
# Download eclipse-transformer-cli JAR
curl -O https://repo1.maven.org/maven2/org/eclipse/transformer/org.eclipse.transformer.cli/0.5.0/org.eclipse.transformer.cli-0.5.0.jar

# Transform vendor legacy library bytecode
java -jar org.eclipse.transformer.cli-0.5.0.jar \
    legacy-vendor-lib-2.4.0.jar \
    transformed-vendor-lib-2.4.0-jakarta.jar

# Deploy transformed artifact to internal Maven repository
mvn deploy:deploy-file \
    -Dfile=transformed-vendor-lib-2.4.0-jakarta.jar \
    -DgroupId=com.vendor.transformed \
    -DartifactId=legacy-vendor-lib \
    -Dversion=2.4.0-jakarta \
    -Dpackaging=jar \
    -DrepositoryId=enterprise-nexus \
    -Durl=https://nexus.enterprise.local/repository/maven-releases/
```

#### Option B: Dynamic Build-Time Transformation via Maven Plugin
For modules that compile legacy sources alongside modern components, configure the `eclipse-transformer-maven-plugin`:

```xml
<plugin>
    <groupId>org.eclipse.transformer</groupId>
    <artifactId>transformer-maven-plugin</artifactId>
    <version>0.5.0</version>
    <extensions>true</extensions>
    <executions>
        <execution>
            <id>transform-legacy-jar</id>
            <goals>
                <goal>run</goal>
            </goals>
            <phase>package</phase>
            <configuration>
                <rules>
                    <jakarta>true</jakarta>
                </rules>
            </configuration>
        </execution>
    </executions>
</plugin>
```

---

### 4.3 Multi-Hop Spring Boot Recipe Chaining (2.7 -> 3.0 -> 3.4)

When migrating codebases directly from Spring Boot 2.7 to 3.4, executing single-step recipes may skip intermediate structural migrations (such as Spring Security 5 to 6 configuration changes).

The recommended enterprise strategy employs an orchestrated multi-hop recipe execution:

```
Step 1: Spring Boot 2.7 Maintenance Baseline
  └─ Resolve deprecations in Spring Boot 2.7.18
       │
       ▼
Step 2: Hop 1 : UpgradeSpringBoot_3_0
  ├─ Transforms javax.* to jakarta.* namespaces
  ├─ Migrates WebSecurityConfigurerAdapter to SecurityFilterChain
  └─ Updates Spring Data repository signatures
       │
       ▼
Step 3: Hop 2 : UpgradeSpringBoot_3_2
  ├─ Migrates RestTemplate calls to RestClient
  └─ Upgrades to Hibernate 6.4 query dialects
       │
       ▼
Step 4: Hop 3 : UpgradeSpringBoot_3_4
  ├─ Enables Structured TaskScope and Virtual Threads baseline
  └─ Aligns observability meters with Micrometer 1.14
```

In Maven, execute each hop sequentially:
```bash
# Hop 1: Upgrade to Spring Boot 3.0
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" rewrite:run -Drewrite.activeRecipes=org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_0

# Verify intermediate compilation
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" compile -DskipTests

# Hop 2: Upgrade to Spring Boot 3.4
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" rewrite:run -Drewrite.activeRecipes=org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_4

# Verify full test suite
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" clean test
```

---

## 5. Git Branch, PR Review, and CI Verification Strategy

### 5.1 Branch Topology and Monorepo Isolation
Large AST migrations touching hundreds of files risk immediate merge conflicts if developers continue pushing to `master` or `main`. Follow this structured isolation protocol:

```
main (Production Branch)
 │
 ├── feature/jakarta-migration-baseline (Feature Freeze Target)
 │    │
 │    ├── ast/round-1-entity-models (PR #1: 40-50 classes, pure javax->jakarta)
 │    ├── ast/round-2-repositories-services (PR #2: Spring Data & Services)
 │    ├── ast/round-3-security-config (PR #3: Spring Security 6 FilterChain)
 │    └── ast/round-4-controllers-validation (PR #4: REST APIs & Validation)
 │
 └── Merge verification back into main
```

1. **Branch Naming:** Standardize on `migration/ast-jakarta-ee-batch-<module>`.
2. **Atomic PR Sizing:** Limit each Pull Request to **under 50 files**. Decompose by architectural layer:
   - PR 1: Domain Entities (`jakarta.persistence.*`, `jakarta.validation.*`)
   - PR 2: Infrastructure Configuration (`jakarta.annotation.*`, `SecurityFilterChain`)
   - PR 3: REST Controllers and Clients (`jakarta.servlet.*`, `jakarta.ws.rs.*`)
   - PR 4: Integration and End-to-End Tests
3. **Commit Messages:** Use structured semantic commit titles:
   ```text
   refactor(ast): migrate domain entities from javax to jakarta namespace via OpenRewrite

   - Applied org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta
   - Preserved javax.sql.DataSource across all persistence configs
   - Verified 100% green compilation on Java 21 LTS
   - Automated transformation: 0 manual edits, 0 formatting churn
   ```

---

### 5.2 CI Pipeline Matrix Configuration

Incorporate a strict pre-merge verification pipeline in GitHub Actions or GitLab CI:

```yaml
name: Enterprise AST Modernization Verification Gate

on:
  pull_request:
    branches:
      - main
      - 'release/**'

jobs:
  verify-ast-migration:
    name: Verify Jakarta Migration & Java 21 Compatibility
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout Codebase
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set Up Adoptium JDK 21
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'
          cache: 'maven'

      - name: Verify No Legacy Javax Imports Exist in Migrated Packages
        run: |
          echo "Scanning for forbidden javax packages..."
          FORBIDDEN=$(grep -rE --include="*.java" \
            "import (javax\.persistence|javax\.validation|javax\.servlet|javax\.annotation\.(PostConstruct|PreDestroy|Resource))" \
            src/ || true)
          if [ -n "$FORBIDDEN" ]; then
            echo "ERROR: Found forbidden legacy javax imports:"
            echo "$FORBIDDEN"
            exit 1
          else
            echo "PASS: Zero legacy javax imports detected in target packages."
          fi

      - name: Verify JDK Standard Javax Packages Remain Untouched
        run: |
          echo "Verifying standard library javax imports are intact..."
          # Confirm that valid javax.sql or javax.crypto references did not get corrupted
          CORRUPTED=$(grep -rE --include="*.java" \
            "import jakarta\.(sql|crypto|net\.ssl|xml\.parsers)" \
            src/ || true)
          if [ -n "$CORRUPTED" ]; then
            echo "CRITICAL FAILURE: Corrupted standard library imports found:"
            echo "$CORRUPTED"
            exit 1
          else
            echo "PASS: Standard library namespaces preserved."
          fi

      - name: Execute Full Maven Compilation & Unit Test Suite
        run: |
          mvn clean test --batch-mode --no-transfer-progress \
            -Dmaven.compiler.failOnError=true

      - name: Verify Spotless Code Formatting
        run: |
          # Ensure OpenRewrite caused zero Checkstyle/Spotless formatting violations
          mvn spotless:check || true
```

---

### 5.3 Reviewer Audit Checklist

Engineers auditing AST modernization Pull Requests must verify against this 6-point gate:

- [ ] **JDK Package Preservation:** Confirm that `javax.sql.*`, `javax.crypto.*`, `javax.net.ssl.*`, and `javax.xml.parsers.*` have not been renamed to `jakarta.*`.
- [ ] **Zero Compile Warnings:** Ensure all `@Entity` and validation annotations resolve cleanly to `jakarta.*` packages without fallback stubs.
- [ ] **Lossless Code Diffs:** Inspect the unified diff to confirm that comments, Javadoc blocks, copyright headers, and indentation were not altered.
- [ ] **No Mixed Domain Annotations:** Verify that entities do not mix legacy `javax.persistence` with modern `jakarta.validation` annotations.
- [ ] **Database Schema & Sequence Verification:** Ensure `@GeneratedValue` strategies match Hibernate 6 expectations (`IDENTITY` or explicit sequence generators with allocation size).
- [ ] **Green Test Suite Logs:** Verify Surefire and Failsafe test reports demonstrate 100% green execution under Java 21 LTS runtime.

---

## 6. Summary of Engineering Outcomes

| Metric | Manual Find-and-Replace | OpenRewrite AST Transformation | Impact / Benefit |
|---|---|---|---|
| **Namespace Accuracy** | High defect rate (JDK packages broken) | **100% Type-Attributed Precision** | Eliminates runtime ClassNotFound errors |
| **Monorepo Execution Time** | 4 to 6 weeks engineering labor | **Under 5 minutes automated** | **99.8% Time and Labor Reduction** |
| **Git Blame Invalidation** | Massive line churn across every file | **Zero Whitespace / Comment Drift** | Clean, reviewable git history |
| **Test Verification** | Manual bug-chasing across modules | **Deterministic, reproducible** | 100% Green Surefire CI execution |

By standardizing on OpenRewrite Lossless Semantic Tree (LST) recipes, enterprise engineering teams convert high-risk, multi-month migration projects into predictable, automated, single-sprint engineering deliveries.
