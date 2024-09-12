from service_base import ServiceBase


class Service(ServiceBase):

    @staticmethod
    def filterPresentRelatedRule(rule):
        pass

    @staticmethod
    def getDependencyKeysInRule(rule):
        pass

    @staticmethod
    def getValidationErrorTemplateMessages():
        pass

    @staticmethod
    def getValidationErrors(data, ruleLists, names, messages):
        pass

    @staticmethod
    def hasArrayObjectRuleInRuleList(ruleList):
        pass

    @staticmethod
    def removeDependencyKeySymbolInRule(rule):
        pass

    @staticmethod
    def getResponseBody(result, totalErrors):
        pass
