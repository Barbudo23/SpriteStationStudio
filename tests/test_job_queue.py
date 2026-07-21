import time
import unittest
from core.jobs.job_queue import Job, JobQueue, JobStatus

class JobQueueTests(unittest.TestCase):
    def test_job_finishes(self):
        queue = JobQueue()
        job = Job("demo", lambda: 7)
        queue.submit(job)
        deadline = time.time() + 2
        while job.status in {JobStatus.WAITING, JobStatus.RUNNING} and time.time() < deadline:
            time.sleep(0.01)
        queue.shutdown()
        self.assertEqual(job.status, JobStatus.FINISHED)
        self.assertEqual(job.result, 7)

if __name__ == "__main__":
    unittest.main()
