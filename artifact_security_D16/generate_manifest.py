import hashlib
import os

files = [
    ".gitignore",
    "README.md",
    "pom.xml",
    "requirements.txt",
    "generate_manifest.py",
    "output/security_metrics.json",
    "output/spring_security_rbac_audit_report.md",
    "src/main/resources/application.properties",
    "src/main/java/com/albidox/security/SecurityApplication.java",
    "src/main/java/com/albidox/security/config/SecurityConfig.java",
    "src/main/java/com/albidox/security/config/JwtAuthenticationEntryPoint.java",
    "src/main/java/com/albidox/security/config/JwtAccessDeniedHandler.java",
    "src/main/java/com/albidox/security/config/SecurityGlobalExceptionHandler.java",
    "src/main/java/com/albidox/security/security/JwtAuthenticationFilter.java",
    "src/main/java/com/albidox/security/security/JwtTokenProvider.java",
    "src/main/java/com/albidox/security/security/TokenValidationStatus.java",
    "src/main/java/com/albidox/security/dto/LoginRequest.java",
    "src/main/java/com/albidox/security/dto/LoginResponse.java",
    "src/main/java/com/albidox/security/dto/ApiResponse.java",
    "src/main/java/com/albidox/security/controller/AuthController.java",
    "src/main/java/com/albidox/security/controller/UserController.java",
    "src/main/java/com/albidox/security/controller/ManagerController.java",
    "src/main/java/com/albidox/security/controller/AdminController.java",
    "src/test/java/com/albidox/security/SecurityIntegrationTest.java",
    "src/test/java/com/albidox/security/SecurityStressProbeTest.java",
]

lines = []
for rel in sorted(files):
    with open(rel, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    lines.append(f"{digest}  {rel.replace(os.sep, '/')}")

manifest = "\n".join(lines) + "\n"
with open("output/SHA256SUMS.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write(manifest)
print(f"Generated output/SHA256SUMS.txt with {len(lines)} entries.")
