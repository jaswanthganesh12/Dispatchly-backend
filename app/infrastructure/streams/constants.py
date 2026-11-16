
CRITICAL_STREAM = "dispatchly:emails:critical"
NORMAL_STREAM = "dispatchly:emails:normal"
BULK_STREAM = "dispatchly:emails:bulk"

CONSUMER_GROUP = "dispatchly-workers"


def get_stream_for_priority(priority: int) -> str:
    if not 1 <= priority <= 10:
        raise ValueError("Priority must be between 1 and 10")

    if priority >= 8:
        return CRITICAL_STREAM

    if priority >= 4:
        return NORMAL_STREAM

    return BULK_STREAM
