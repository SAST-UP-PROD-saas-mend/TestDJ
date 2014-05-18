UNKNOWN = 0
PENDING = 1
FAILED = 2
SUCCESS = 3

class ResultUnavailable(Exception):
    pass

class InvalidCacheBackendError(Exception):
    pass

class TaskResult(object):
    def __init__(self, backend, task_id):
        self._backend = backend
        self.task_id = task_id

    def __repr__(self):
        return '<TaskResult %s - %r>' % (self.alias, self.task_id)

    @property
    def alias(self):
        return self._backend.alias

    def get_status(self, **kwargs):
        return self._backend.status(self.task_id, **kwargs)

    def get_result(self, **kwargs):
        return self._backend.get_result(self.task_id, **kwargs)


class BaseBackend(object):
    def __init__(self, alias, **kwargs):
        self.alias = alias

    def get_status(self, task_id):
        """
        The current status of the task.

        PENDING: the task is currently in-queue, and waiting to be ran.
        FAILED: the task attempted to run, but failed for some reason
        SUCCESS: the task successfully ran
        UNKNOWN: unable to determine the status of the task
        """
        raise NotImplementedError

    def get_result(self, task_id):
        """
        If the task has ran and returned a result, return that result.

        If not, raise a ResultUnavailable exception
        """
        raise NotImplementedError

    def delay(self, task, *args, **kwargs):
        """
        Enqueue provided task
        """
        raise NotImplementedError

class DummyTaskResult(TaskResult):
    def __init__(self, backend, task_id, status, result):
        super(DummyTaskResult, self).__init__(backend, task_id)
        self._status = status
        self._result = result

    def get_status(self, **kwargs):
        return self._status

    def get_result(self, **kwargs):
        return self._result

class DummyTaskBackend(BaseBackend):
    def __init__(self, *args, **kwargs):
        super(DummyTaskBackend, self).__init__(*args, **kwargs)
        self._next_task_id = 1

    def get_status(self, task_id):
        return UNKNOWN

    def delay(self, task, *args, **kwargs):
        task_id = self._next_task_id
        self._next_task_id += 1
        result = None
        status = SUCCESS
        try:
            result = task(*args, **kwargs)
        except Exception as e:
            result = e
            status = FAILED

        return DummyTaskResult(self, task_id, status, result)
