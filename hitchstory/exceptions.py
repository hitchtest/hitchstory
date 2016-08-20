class HitchStoryException(Exception):
    pass


class StepNotFound(HitchStoryException):
    """
    Step in story has no corresponding method in engine.
    """
    pass


class StepException(HitchStoryException):
    """
    Exception relating to a particular step.
    """
    pass


class StepNotCallable(StepException):
    """
    The step you tried to call is not a python method.
    """
    pass


class StepContainsInvalidValidator(StepException):
    """
    Step contains a validator for which there is no corresponding argument.
    """
    pass


class StepArgumentWithoutValidatorContainsComplexData(StepException):
    """
    Step arguments that contain hierarchical data like so:

    - step name:
        complex argument:
          x: 1
          y: 2
        complex argument:
          - list item
          - list item

    need validators.
    """
    pass
