# Artifact C1: Spring Boot Hibernate N+1 Query Elimination Benchmark

A reproducible, automated Spring Boot 3.4 / Java 21 verification package demonstrating the reproduction, forensic interception, and elimination of the classic Hibernate N+1 query performance bottleneck.

## Project Overview

- **Framework**: Spring Boot 3.4.1, Spring Data JPA, Hibernate 6.6.4.Final
- **Language**: Java 21 (Adoptium OpenJDK 21 LTS)
- **Database**: H2 In-Memory (`jdbc:h2:mem:n1db`)
- **Domain Model**: 1:N Parent-Child Relationship (`User` 1 : N `Order`)
- **Seeded Dataset**: 50 Users, 5 Orders each (250 total Orders hydrated via `CommandLineRunner`)

---

## The Defect: Hibernate N+1 Pathology

In standard Spring Data JPA configurations where parent-child collections are marked `FetchType.LAZY`:
1. Calling `userRepository.findAll()` fires **1 query** to fetch all 50 `User` entities:
   ```sql
   select u1_0.id,u1_0.email,u1_0.name from users u1_0;
   ```
2. When accessing `user.getOrders().size()` during DTO serialization or service logic, Hibernate encounters uninitialized lazy proxies and fires **50 individual queries** (1 per user):
   ```sql
   select o1_0.user_id,o1_0.id,o1_0.amount,o1_0.status from orders o1_0 where o1_0.user_id=?;
   ```
3. **Total Database Queries**: `1 + 50 = 51 queries`. In production environments with thousands of users, this cascades into thousands of database round-trips, saturating HikariCP connection pools and causing cascading timeout crashes.

---

## The Minimal Fix: Declarative `@EntityGraph`

By applying a minimal 4-line patch to `UserRepository.java`, Hibernate is instructed to fetch the lazy collection eagerly using a single SQL `LEFT JOIN`:

```java
@EntityGraph(attributePaths = {"orders"})
List<User> findAll();
```

Resulting executed query (**exactly 1 query**):
```sql
select u1_0.id,u1_0.email,u1_0.name,o1_0.user_id,o1_0.id,o1_0.amount,o1_0.status 
from users u1_0 
left join orders o1_0 on u1_0.id=o1_0.user_id;
```

---

## Empirical Benchmark Results

| Metric | Unoptimized Baseline (Before) | EntityGraph Optimization (After) | Delta / Impact |
|---|---|---|---|
| **SQL Queries Fired** | 51 queries | **1 query** | **98.0% Query Reduction** |
| **Database Round-Trips** | 51 round-trips | **1 round-trip** | 50 network round-trips saved |
| **Response Duration (H2)** | 5.46 ms (mean) / 7.79 ms (p95) | 3.83 ms (mean) / 5.78 ms (p95) | **1.4x Faster (In-Memory)** |
| **Distributed Environment Latency (1ms RTT)** | ~56.46 ms | ~4.83 ms | **11.7x Faster Latency** |
| **HikariCP Leases** | 51 connection requests | 1 connection lease | Eliminates pool exhaustion |
| **Hydration Integrity** | 50 Users, 250 Orders | 50 Users, 250 Orders | 100% Identical Output |
| **Surefire Test Suite** | 3 / 3 passed | 3 / 3 passed | 100% Green Verification |

---

## Project Structure

```
artifact_springboot_C1/
├── SPRING_BOOT_N1_REMEDIATION_REPORT.md   # Flagship client deliverable & architectural guide
├── jpa_performance_production_guide.md    # Production JPA Architecture & OSIV Guide (Round 2)
├── README.md                              # Project runbook and commands
├── pom.xml                                # Spring Boot 3.4 / Java 21 build descriptor
├── fix.patch                              # Minimal clean repository diff
├── benchmark_summary.md                   # Empirical metric comparison matrix
├── src/
│   ├── main/java/com/ashfaq/n1/
│   │   ├── Application.java               # Spring Boot Application entrypoint
│   │   ├── config/DataSeeder.java         # 50 users x 5 orders data seeder
│   │   ├── controller/UserController.java # REST endpoint /api/users
│   │   ├── dto/UserResponseDto.java       # Immutable Java 21 Record DTO
│   │   ├── model/Order.java               # Order child entity (LAZY fetch)
│   │   ├── model/User.java                # User parent entity (OneToMany LAZY)
│   │   ├── repository/UserRepository.java # Spring Data JPA repo with @EntityGraph
│   │   ├── service/UserService.java       # Transactional boundary service
│   │   └── tracker/SqlStatementCountTracker.java # Hibernate StatementInspector
│   └── test/java/com/ashfaq/n1/
│       └── UserN1QueryTest.java           # Statement counting assertions
└── output/
    ├── jpa_performance_production_guide.md# Production JPA Architecture & OSIV Guide
    ├── sql_log_before.txt                 # Baseline 51 queries evidence
    ├── sql_log_after.txt                  # Optimized 1 query evidence
    ├── test_before_n1.txt                 # Baseline endpoint verification trace
    ├── test_after_fixed.txt               # Optimized endpoint verification trace
    ├── fix.patch                          # Exported repository patch
    ├── surefire_report.txt                # Surefire execution log (3/3 passed)
    └── TEST-com.ashfaq.n1.UserN1QueryTest.xml # Surefire XML report
```

---

## Verification & Execution Commands

### 1. Execute Complete Test Suite
```bash
"C:\Program Files\apache-maven-3.9.16\bin\mvn.cmd" clean test
```

### 2. Verify Output Logs
```bash
# Baseline SQL log (51 queries)
cat output/sql_log_before.txt

# Optimized SQL log (1 query)
cat output/sql_log_after.txt
```

### 3. Verify Patch Application
```bash
git apply --check fix.patch
```

---
Author: Sk Ashfaq Bux (`github.com/Albidox`)
Portfolio Artifact C1: Spring Boot & Distributed Systems Backend Engineering
