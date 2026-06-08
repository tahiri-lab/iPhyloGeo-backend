the format goes as follows:
    {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "hostname": socket.gethostname(),
    }

    timestamp = the time of the log
    level = what type of log it is {
        info: normal logs,
        debug: dev specific info,
        warning: something seems wrong and might be a problem,
        error: an error but things still work,
        critical (or exception): a crash
    }

first step when adding the logger is to make sure that 
    from utils.logger import get_logger
    logger = get_logger(__name__)
is present in the file you need the logger in.
    the fist line is just to import it the second is to automatically set the name of the module

when you want to log something or when you want to just add a print()
    # potential print()
    print("Error in validate_file :", e)
use this instead
    logger.error("Error in validate_file: %s", e)
    or in pseudo code
    logger.[level_of_your_log]("[log_message]", [variable_if_any])