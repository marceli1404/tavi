"""Static fail-safe contract for the optional PowerShell yellow-border workaround.

This does not execute Windows PowerShell or validate actual Windows process
behaviour. Run the script manually on a Windows host for live verification.
"""
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parent / 'scripts' / 'fix-codex-yellow-border.ps1'


class CleanupContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = SCRIPT.read_text(encoding='utf-8')

    def test_no_silent_kills_and_user_idle_assertion(self):
        s = self.code
        self.assertIn('if ($Stop -and -not $NoActiveComputerUse)', s)
        self.assertIn('SupportsShouldProcess = $true', s)
        self.assertIn('ShouldProcess(', s)
        self.assertIn('Stop-Process -InputObject $process', s)
        self.assertNotIn('Stop-Process -Name', s)
        self.assertNotIn('taskkill', s.lower())

    def test_only_exact_native_helper_name(self):
        s = self.code
        self.assertIn("Name = 'codex-computer-use.exe'", s)
        self.assertIn("-ieq 'codex-computer-use.exe'", s)
        self.assertNotIn('codex-computer-use-swift.exe', s)

    def test_ownership_and_process_identity_rechecked(self):
        s = self.code
        self.assertIn('Get-AuthenticodeSignature', s)
        self.assertIn('Signature = $signature', s)
        self.assertIn('if ($helpers.Count -ne 1)', s)
        self.assertIn('$current.CreationDate -ne $target.Started', s)
        self.assertIn('$current.ExecutablePath -cne $target.ExecutablePath', s)
        self.assertIn('$current.ParentProcessId -ne $target.ParentId', s)
        self.assertIn('Get-CodexHelperEvidence $current', s)

    def test_no_background_or_permission_changes(self):
        s = self.code.lower()
        for bad in ('register-scheduledtask', 'start-job', 'while ($true)',
                    'set-itemproperty', 'remove-itemproperty',
                    'graphicscapturewithoutborder', 'new-itemproperty'):
            self.assertNotIn(bad, s)


if __name__ == '__main__':
    unittest.main()
