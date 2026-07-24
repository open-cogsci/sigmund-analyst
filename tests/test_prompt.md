## IDE Tools Unit Test — Autonomous Execution Instructions

You are about to run a comprehensive, autonomous unit test of all your IDE tools (excluding note/workspace-related tools). Follow these instructions step by step. Do not skip any steps. Do not ask for clarification — everything you need is below.

### Phase 0: Preparation

1. Check that the current workind directory is `/tmp/ide_tool_test`. If it is not, abort.
2. **Store the full test instructions** as a persistent note with label `"test_instructions"`. The content of this note should be a description of all tests, including steps and verification procedures. The descriptions should be detailed enough for you to run the tests.
3. **Store a todo list** as a persistent note with label `"test_todo"`. The todo list should contain the following items, all initially unchecked:
   - [ ] Test 1: `ide_execute_shell_command` — create temp directory
   - [ ] Test 2: `ide_write_file` — write a file and verify content
   - [ ] Test 3: `ide_inspect_files` — inspect a file and verify content
   - [ ] Test 4: `ide_list_files` — list files and verify contents
   - [ ] Test 5: `ide_list_files` (recursive) — list files recursively
   - [ ] Test 6: `ide_open_file` — open a file without error
   - [ ] Test 7: `ide_execute_code` — execute Python code and verify output
   - [ ] Test 8: `ide_execute_code` — execute code that writes a file, then verify
   - [ ] Test 9: `ide_execute_shell_command` — rename a file, then verify
   - [ ] Test 10: `ide_execute_shell_command` — run command with `working_directory` parameter
   - [ ] Test 11: `ide_write_file` — overwrite an existing file, then verify
   - [ ] Test 12: `ide_inspect_files` — inspect multiple files at once
   - [ ] Test 13: Working directory consistency check
   - [ ] Test 14: `ide_execute_shell_command` — cleanup temp directory
   - [ ] Test 15: Final verification and report
4. **Clear the temporary test directory** using `ide_execute_shell_command`:
   - Run: `rm -rf /tmp/ide_tool_test/*`.
   - This directory (`/tmp/ide_tool_test`) will be used for all subsequent tests.
5. **Mark Test 1 as complete** by updating the `"test_todo"` note. Replace `- [ ] Test 1` with `- [x] Test 1`. Keep all other items unchanged.

### Phase 1: File Writing and Reading

**Test 2: `ide_write_file` — write a file and verify content**

- Call `ide_write_file` with path `/tmp/ide_tool_test/hello.txt` and content:
  ```
  Hello, World!
  This is a test file.
  ```
- Verify: Call `ide_execute_shell_command` with command `cat /tmp/ide_tool_test/hello.txt`. Confirm the output contains both lines of text.
- Update the `"test_todo"` note to mark Test 2 as complete.

**Test 3: `ide_inspect_files` — inspect a file and verify content**

- Call `ide_inspect_files` with paths `["/tmp/ide_tool_test/hello.txt"]`.
- Verify: Confirm the returned content matches:
  ```
  Hello, World!
  This is a test file.
  ```
- Update the `"test_todo"` note to mark Test 3 as complete.

### Phase 2: Directory Listing

**Test 4: `ide_list_files` — list files and verify contents**

- First, create additional files using `ide_write_file`:
  - `/tmp/ide_tool_test/file_a.txt` with content `Content A`
  - `/tmp/ide_tool_test/file_b.txt` with content `Content B`
- Call `ide_list_files` with path `/tmp/ide_tool_test`.
- Verify: Confirm the listing includes `hello.txt`, `file_a.txt`, and `file_b.txt`.
- Update the `"test_todo"` note to mark Test 4 as complete.

**Test 5: `ide_list_files` (recursive) — list files recursively**

- Create a subdirectory structure using `ide_execute_shell_command`:
  ```sh
  mkdir -p /tmp/ide_tool_test/subdir
  ```
- Create a file in the subdirectory using `ide_write_file`:
  - `/tmp/ide_tool_test/subdir/nested.txt` with content `Nested content`
- Call `ide_list_files` with path `/tmp/ide_tool_test` and `recursive: true`.
- Verify: Confirm the listing includes `subdir/nested.txt` (or equivalent nested path representation).
- Update the `"test_todo"` note to mark Test 5 as complete.

### Phase 3: File Opening

**Test 6: `ide_open_file` — open a file without error**

- Call `ide_open_file` with path `/tmp/ide_tool_test/hello.txt`.
- Verify: Confirm the tool call completes without error. (This tool opens the file in the editor; success means no error was returned.)
- Update the `"test_todo"` note to mark Test 6 as complete.

### Phase 4: Code Execution

**Test 7: `ide_execute_code` — execute Python code and verify output**

- Call `ide_execute_code` with language `python` and the following code:
  ```python
  result = 2 + 2
  print(f"The result is {result}")
  ```
- Verify: Confirm the output contains `The result is 4`.
- Update the `"test_todo"` note to mark Test 7 as complete.

**Test 8: `ide_execute_code` — execute code that writes a file, then verify**

- Call `ide_execute_code` with language `python` and the following code:
  ```python
  with open("code_created.txt", "w") as f:
      f.write("Created by ide_execute_code")
  print("File written successfully")
  ```
- Verify: Call `ide_inspect_files` with paths `["/tmp/ide_tool_test/code_created.txt"]`. Confirm the content is `Created by ide_execute_code`.
- Update the `"test_todo"` note to mark Test 8 as complete.

### Phase 5: Shell Command Features

**Test 9: `ide_execute_shell_command` — rename a file, then verify**

- Call `ide_execute_shell_command` with command `mv file_a.txt file_renamed.txt`.
- Verify: Call `ide_list_files` with path `/tmp/ide_tool_test`. Confirm `file_renamed.txt` appears and `file_a.txt` does not.
- Update the `"test_todo"` note to mark Test 9 as complete.

**Test 10: `ide_execute_shell_command` — run command with `working_directory` parameter**

- Call `ide_execute_shell_command` with command `pwd` and `working_directory` set to `/tmp/ide_tool_test`.
- Verify: Confirm the output contains `/tmp/ide_tool_test`.
- Update the `"test_todo"` note to mark Test 10 as complete.

### Phase 6: File Overwrite and Multi-File Inspection

**Test 11: `ide_write_file` — overwrite an existing file, then verify**

- Call `ide_write_file` with path `hello.txt` and content `Overwritten content.`
- Verify: Call `ide_inspect_files` with paths `["/tmp/ide_tool_test/hello.txt"]`. Confirm the content is `Overwritten content.` (the old content should be gone).
- Update the `"test_todo"` note to mark Test 11 as complete.

**Test 12: `ide_inspect_files` — inspect multiple files at once**

- Call `ide_inspect_files` with paths `["/tmp/ide_tool_test/file_b.txt", "/tmp/ide_tool_test/file_renamed.txt", "/tmp/ide_tool_test/code_created.txt"]`.
- Verify: Confirm that all three files' contents are returned. `file_b.txt` should contain `Content B`, `file_renamed.txt` should contain `Content A`, and `code_created.txt` should contain `Created by ide_execute_code`.
- Update the `"test_todo"` note to mark Test 12 as complete.

### Phase 7: Working Directory Consistency

**Test 13: Working directory consistency check**

- Call `ide_execute_shell_command` with command `pwd` (no `working_directory` override — use the default).
- Call `ide_execute_code` with language `python` and code:
  ```python
  import os
  print(os.getcwd())
  ```
- Verify: Confirm that both outputs show the same directory path. Report what the working directory is.
- Update the `"test_todo"` note to mark Test 13 as complete.

### Phase 8: Cleanup

**Test 14: `ide_execute_shell_command` — cleanup temp directory**

- Call `ide_execute_shell_command` with command `rm -rf /tmp/ide_tool_test/*`.
- Verify: Call `ide_list_files` with path `/tmp/ide_tool_test`. This should show an empty folder.
- Update the `"test_todo"` note to mark Test 14 as complete.

### Phase 9: Final Report

**Test 15: Final verification and report**

- Inspect the `"test_todo"` note. Confirm all items are marked `[x]`.
- Remove the `"test_instructions"` note (using `remove_note`).
- Remove the `"test_todo"` note (using `remove_note`).
- Provide a final summary report in your response that includes:
  - Total number of tests run
  - List of each test and whether it passed or failed
  - Any issues or anomalies encountered
  - The working directory as observed during Test 13
  - Confirmation that all persistent notes were cleaned up

### Important Rules

- **Between tests**, do NOT clean up the temp directory unless a specific test instructs you to. Tests are designed to build on each other's state where needed.
- **After each test**, always update the `"test_todo"` note before proceeding to the next test.
- **If a test fails**, still update the todo list (mark it with `[~]` to indicate failure) and continue to the next test. Note the failure in your final report.
- **Be autonomous**: Do not ask the user any questions. If something unexpected happens, note it and continue.
- **Verification is key**: Every test must include a verification step where you check the expected outcome using a tool call. Do not assume success — verify it.
