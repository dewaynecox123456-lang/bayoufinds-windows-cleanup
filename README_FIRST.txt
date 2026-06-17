BayouFinds Windows Cleanup Tool v1.2 - Sean Dev Test
====================================================

Sean,

This is a development build for testing. It is not a final release package yet.

Please use the files in this folder to test the cleanup tool and fill out the
Sean Test Validation Checklist. Send the completed checklist back to Dewayne
when you are done.

Start here
----------

Double-click START_CLEANUP_GUI.bat.

This opens the BayouFinds desktop GUI. It starts with a splash screen, then
shows the User Agreement if it has not already been accepted. After that, use
the main window to select actions and review the output/status box.

Recommended test order
----------------------

Use START_CLEANUP_GUI.bat and run these actions in order:

1. Check license
   This checks whether the local BayouFinds license file is recognized.

2. Preview cleanup
   Run Preview first. Preview checks what safe junk can be cleaned without
   deleting files.

3. Back up browser bookmarks
   Back up browser bookmarks before cleanup.

4. Run safe cleanup
   Run Safe Cleanup only after Preview.

The CLI menu and separate BAT launchers are still included for direct testing:

- START_CLEANUP_TOOL.bat
- START_HERE.bat
- RUN_LICENSE_CHECK.bat
- RUN_PREVIEW.bat
- RUN_BOOKMARK_BACKUP.bat
- RUN_SAFE_CLEANUP.bat

Important safety notes
----------------------

- Personal files are protected.
- Documents are not touched.
- Pictures are not touched.
- Downloads are not touched.
- Desktop files are not touched.
- The tool does not clean the registry.
- The tool does not run risky optimizations.
- The tool does not close or kill browsers automatically.

Reports
-------

Reports are saved here:

Desktop\BayouFinds_Cleanup_Logs

The tool creates:

- HTML report for easy viewing
- JSON report for support/debugging
- LOG file for raw operation details

If something is confusing or does not feel safe, write that in the checklist.
