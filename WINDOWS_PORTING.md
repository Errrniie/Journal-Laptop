# Windows Porting Plan

## Overview

The Journal application is already built with cross-platform technologies:

- Python
- PyQt6
- Requests
- Matplotlib
- JSON files

The application does not need to be rewritten for Windows. Most models, feature services, widgets, analytics, and API payload handling can remain unchanged. The main work is adapting the application shell, file locations, configuration, credentials, networking behavior, packaging, and release process.

This document describes the high-level changes needed for a dependable Windows version.

## 1. Application startup

- Keep `main.py` as the shared application entry point.
- Retain Linux-specific startup behavior only behind a platform check.
- Do not use `run_app.sh` on Windows.
- Do not install or package `ernesto-journal.desktop` on Windows.
- Add a Windows development launcher if desired, such as `run_app.ps1` or `run_app.bat`.
- Make sure startup does not depend on the repository being located at a particular absolute path.
- Confirm that all required directories and files are initialized when the app runs for the first time.

## 2. File and directory locations

The current relative paths work when the application is launched from the repository, but they are not reliable for an installed Windows application.

- Determine the application resource directory from `__file__` or the PyInstaller bundle location.
- Store bundled, read-only resources with the application:
  - Application icon
  - Default configuration values
  - Other static assets
- Store writable user data in a per-user Windows directory, preferably:

  ```text
  %LOCALAPPDATA%\Ernesto\Journal\
  ```

- Move or redirect these writable files to that directory:
  - `lifelog.json`
  - `settings.json`
  - `workout_templates.json`
  - Log files
  - Automatic backups
- Create the directory on first launch.
- Add a one-time migration path for data previously stored in the repository's `data` directory.
- Never assume that the installation directory is writable.
- Remove hardcoded Linux paths, including the `.cursor/debug.log` paths in the workout widget and workout template service.

## 3. Central path configuration

- Introduce one application-path module responsible for locating:
  - Project or bundle resources
  - User data
  - Settings
  - Templates
  - Logs
  - Backups
- Pass resolved paths into storage and services instead of scattering path strings throughout the application.
- Keep path handling based on `pathlib.Path`.
- Avoid manual `/` or `\` path concatenation.

## 4. Application data and migration

- Preserve compatibility with the current `lifelog.json` schema.
- Back up existing data before performing a schema or location migration.
- Use atomic writes for settings and template files as well as the primary life-log file.
- If JSON is corrupted, preserve the damaged file and clearly notify the user instead of silently presenting an empty journal.
- Add an explicit data export/import or backup/restore option for moving data between Linux and Windows.
- Define how remote data and local cached data should be reconciled on the first Windows launch.

## 5. API configuration

- Move the API base URL out of the `APIClient` class constant and into application configuration.
- Provide a safe default production URL.
- Allow a development or test URL without editing source code.
- Validate the URL before saving or using it.
- Continue using HTTPS and the existing `x-api-key` header unless the server contract changes.
- Do not start remote synchronization when an API key is absent.
- Display whether the application is operating online, offline, or from cached data.

## 6. API request reliability

- Add explicit connection and response timeouts to all HTTP requests.
- Add limited retries with backoff for temporary connection errors and suitable `5xx` responses.
- Do not retry validation, authentication, conflict, or other permanent client errors automatically.
- Convert low-level network errors into clear user-facing messages.
- Ensure a failed API read never replaces valid local cached data with an empty result.
- Log request method, endpoint, status, and duration without logging the API key or private journal content.
- Decide and document which system is authoritative for each feature:
  - Journal: currently remote when configured
  - Tasks: currently remote when configured
  - Workouts: currently remote when configured
  - Sleep: currently local
  - Workout templates: currently local

## 7. Background synchronization

- Prevent rapid date changes from replacing or destroying a still-running `QThread`.
- Keep references to active workers until they finish.
- Ignore results belonging to an older date or request generation.
- Consider using a worker queue or `QThreadPool` for controlled concurrency.
- Disable or debounce repeated sync operations while an equivalent request is running.
- Restore the normal cursor and UI state after success, failure, cancellation, or an exception.
- Surface synchronization errors instead of only printing them to the console.
- Ensure the application can close cleanly while workers are active.

## 8. API key and secrets

- Do not include a real API key in the repository, executable, installer, or default settings file.
- Avoid keeping the production key in plaintext JSON for the distributed application.
- Prefer Windows Credential Manager through a library such as `keyring`.
- If plaintext storage remains available as a fallback, explain the limitation to the user.
- Never write authentication headers or API keys to logs or error dialogs.
- Add a way to remove or replace the saved credential.
- Treat a `401` or `403` response as a credential/configuration issue and present an actionable message.

## 9. Windows UI behavior

- Verify layouts at Windows display scaling levels such as 100%, 125%, 150%, and 200%.
- Test standard and high-resolution monitors.
- Avoid fixed sizes where they cause clipping.
- Verify font sizes, rich-text rendering, scroll areas, dialogs, charts, and tooltips.
- Confirm that keyboard shortcuts do not conflict with common Windows behavior.
- Confirm that date and time widgets behave correctly under Windows locale settings.
- Confirm that file dialogs and Samsung Health CSV selection work as expected.
- Test light and dark Windows themes, even if the application intentionally uses a fixed theme.
- Add a proper `.ico` application icon containing multiple resolutions.

## 10. Logging and error reporting

- Replace development `print` statements with Python's `logging` module.
- Remove the hardcoded Cursor debug log location.
- Write logs to the per-user application data directory.
- Rotate or limit log files so they cannot grow indefinitely.
- Keep private journal, task, workout, and credential content out of normal logs.
- Show concise error dialogs while retaining technical details in the log.
- Add enough startup logging to diagnose missing assets, settings failures, and packaging problems.

## 11. Packaging

- Package the application with PyInstaller before considering a native rewrite.
- Start with a `--onedir` build because it is easier to debug and generally starts faster.
- Use `--windowed` so normal users do not see a console window.
- Include:
  - PyQt6 plugins
  - Matplotlib data files and backends
  - NumPy dependencies
  - Application icons and assets
- Exclude personal data, backups, API keys, logs, `.git`, `.cursor`, `__pycache__`, and development scripts unless intentionally required.
- Add Windows version metadata, company/product naming, and the application icon.
- Test the packaged build on a clean Windows machine without Python installed.
- Consider code signing to reduce SmartScreen warnings for distributed releases.

An initial development command would resemble:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --windowed --onedir --name Journal --icon journal.ico main.py
```

A maintained PyInstaller specification file should ultimately replace an ad hoc command.

## 12. Windows installer

- Use an installer builder such as Inno Setup or WiX after the packaged application is stable.
- Prefer a per-user installation unless machine-wide installation is required.
- Install application files separately from writable user data.
- Add Start menu and optional desktop shortcuts.
- Register the correct application icon.
- Provide an uninstaller.
- Do not delete user journals, settings, templates, or backups during a normal uninstall unless the user explicitly requests it.
- Define upgrade behavior so installing a newer version preserves all user data.

## 13. Dependency and environment cleanup

- Pin or constrain dependency versions closely enough to make builds reproducible.
- Establish a supported Python version for Windows builds.
- Remove generated `__pycache__` files from version control.
- Add or update `.gitignore` rules for:
  - Virtual environments
  - PyInstaller build output
  - Installer output
  - Bytecode
  - Logs
  - Personal data
  - Settings containing secrets
  - Data backups
- Separate example/default configuration from real user configuration.

## 14. Testing

- Add offline unit tests for:
  - Model validation
  - JSON serialization and migration
  - Storage merge and replacement behavior
  - Journal page operations
  - Task mapping
  - Workout volume and validation
  - Sleep CSV parsing
  - Settings and path handling
- Mock the API for normal automated tests.
- Keep live-API integration tests separate and opt-in because they mutate server data.
- Test network timeout, offline, authentication failure, conflict, malformed response, and server-error cases.
- Test first launch with no existing files.
- Test migration from an existing Linux data directory.
- Test application shutdown during an API refresh.
- Test the final executable and installer in a clean Windows environment.

## 15. Documentation

- Replace the current minimal `READ.md` with a real project README.
- Document Windows development setup.
- Document how to run from source.
- Document how to configure or remove the API key.
- Document where Windows user data and logs are stored.
- Document backup, restore, and Linux-to-Windows migration.
- Document how to create the executable and installer.
- Clearly label the existing live-API journal flow script as destructive and opt-in.

## 16. Recommended implementation order

1. Preserve the current working tree and back up personal data.
2. Add centralized, cross-platform application paths.
3. Redirect writable files to the Windows per-user data directory.
4. Remove hardcoded Linux and development paths.
5. Add API timeouts, error handling, and offline state reporting.
6. Make background synchronization lifecycle-safe.
7. Move API credentials to secure storage.
8. Add offline service, storage, and API-mapping tests.
9. Create and validate a PyInstaller `--onedir` build.
10. Test UI scaling and behavior on clean Windows systems.
11. Add an installer, migration flow, and release documentation.
12. Consider signing the executable and installer for wider distribution.

## Expected effort

- Basic Windows source run: a few hours
- First working packaged executable: approximately one to two days
- Reliable personal Windows release: approximately one to two weeks
- Polished broadly distributed release: additional time for installer quality, code signing, migrations, testing, and supportability

The recommended path is to port and package the existing PyQt6 application. A native C# or other Windows-specific rewrite would add substantial cost without providing an immediate functional benefit.
