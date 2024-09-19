class Command:
    def __init__(
        self,
        ex_technique,
        parameters,
        name,
        guid,
        description,
        platforms,
        timeout,
        args,
    ):
        self.ex_technique = ex_technique
        self.parameters = parameters
        self.name = name
        self.guid = guid
        self.description = description
        self.platforms = platforms
        self.timeout = timeout
        self.args = args

    def set_ex_technique(self, ex_technique):
        self.ex_technique = ex_technique

    def set_parameters(self, parameters):
        self.parameters = parameters
