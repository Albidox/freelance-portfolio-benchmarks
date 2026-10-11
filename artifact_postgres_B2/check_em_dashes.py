import os

d = r"C:\AI\knowledge-vault\summary\freelance opportunity\portfolio_samples\artifact_postgres_B2"
found = False
for root, dirs, files in os.walk(d):
    if "venv" in root or ".git" in root:
        continue
    for f in files:
        if f == "check_em_dashes.py":
            continue
        path = os.path.join(root, f)
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
                if "\u2014" in content:
                    print(f"Found em-dash in {path}")
                    found = True
        except Exception:
            pass

if not found:
    print("No em-dashes found.")
