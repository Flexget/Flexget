from flexget.manager import Session


def with_session(func):
    """"Creates a session if one was not passed via keyword argument to the function"""

    def wrapper(*args, **kwargs):
        passed_session = kwargs.get('session')
        if not passed_session:
            session = Session(autoflush=True)
            try:
                return func(*args, session=session, **kwargs)
            finally:
                session.close()
        else:
            return func(*args, **kwargs)
    return wrapper
