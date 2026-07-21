import unittest

from app.task_guard import TaskGuard


class TaskGuardTests(unittest.TestCase):
    def test_duplicate_task_is_rejected_until_finished(self):
        guard = TaskGuard()
        token = guard.begin("scan")
        self.assertIsNotNone(token)
        self.assertIsNone(guard.begin("scan"))
        self.assertTrue(guard.finish(token))
        self.assertIsNotNone(guard.begin("scan"))

    def test_wrong_token_does_not_finish_task(self):
        guard = TaskGuard()
        token = guard.begin("scan")
        from app.task_guard import TaskToken
        self.assertFalse(guard.finish(TaskToken("scan", token.generation + 1)))
        self.assertTrue(guard.is_active("scan"))


if __name__ == "__main__":
    unittest.main()
