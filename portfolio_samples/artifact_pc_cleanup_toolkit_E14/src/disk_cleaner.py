"""Non-destructive Windows disk cleanup engine with locked-file skip resilience.
Strict zero em dash policy enforced.
"""
import os
import time
from typing import List, Dict, Any, Optional
from src.models import CleanTargetType, CleanupRule, CleanupResult, DiskCleanTarget


class WindowsDiskCleaner:
    """Non-destructive Windows disk cleaner handling temp files, browser cache, and memory dumps."""

    def __init__(self):
        pass

    def scan_and_clean(self, rule: CleanupRule) -> CleanupResult:
        """Scan directory and clean matching files according to rule parameters."""
        result = CleanupResult(
            target_type=rule.target_type,
            target_path=rule.target_path
        )
        if not os.path.exists(rule.target_path):
            result.errors.append(f"Directory does not exist: {rule.target_path}")
            return result

        now = time.time()
        age_seconds_limit = rule.max_age_days * 86400

        for root, dirs, files in os.walk(rule.target_path):
            for file_name in files:
                result.files_scanned += 1
                file_path = os.path.join(root, file_name)

                # Extension filter
                if "*.*" not in rule.file_extensions:
                    ext = os.path.splitext(file_name)[1].lower()
                    if ext not in [e.lower() for e in rule.file_extensions]:
                        continue

                try:
                    stat_info = os.stat(file_path)
                    file_size = stat_info.st_size
                    file_mtime = stat_info.st_mtime

                    # Age verification
                    if (now - file_mtime) < age_seconds_limit:
                        continue

                    result.bytes_reclaimed += file_size

                    if not rule.dry_run:
                        os.remove(file_path)
                        result.files_deleted += 1
                    else:
                        result.files_deleted += 1

                except PermissionError:
                    # File currently locked by operating system or active process
                    result.locked_files_skipped += 1
                except FileNotFoundError:
                    # File removed by another concurrent process
                    pass
                except Exception as e:
                    result.errors.append(f"{file_name}: {str(e)}")

            if not rule.recursive:
                break

        return result

    def clean_temp_files(
        self,
        temp_dir: Optional[str] = None,
        dry_run: bool = True,
        max_age_days: int = 1
    ) -> CleanupResult:
        """Prune Windows user and system temporary files."""
        path = temp_dir or os.environ.get("TEMP", "C:\\Windows\\Temp")
        rule = CleanupRule(
            target_type=CleanTargetType.USER_TEMP,
            target_path=path,
            max_age_days=max_age_days,
            dry_run=dry_run,
            recursive=True
        )
        return self.scan_and_clean(rule)

    def clean_browser_cache(
        self,
        cache_dir: Optional[str] = None,
        dry_run: bool = True
    ) -> CleanupResult:
        """Scavenge Chromium and browser cache artifacts."""
        path = cache_dir or os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache")
        rule = CleanupRule(
            target_type=CleanTargetType.BROWSER_CACHE,
            target_path=path,
            max_age_days=0,
            dry_run=dry_run,
            recursive=True
        )
        return self.scan_and_clean(rule)

    def clean_crash_dumps(
        self,
        dump_dir: Optional[str] = None,
        dry_run: bool = True
    ) -> CleanupResult:
        """Remove Windows memory crash dumps (.dmp files)."""
        path = dump_dir or os.path.expandvars(r"%LOCALAPPDATA%\CrashDumps")
        rule = CleanupRule(
            target_type=CleanTargetType.CRASH_DUMPS,
            target_path=path,
            file_extensions=[".dmp", ".tmp"],
            max_age_days=0,
            dry_run=dry_run,
            recursive=False
        )
        return self.scan_and_clean(rule)
