import copy
import re

from src.service_base import ServiceBase
from src.validation.validator import getValidator


class Service(ServiceBase):

    @staticmethod
    def filterPresentRelatedRule(rule):
        rule = copy.deepcopy(rule)
        hasPresentRule = False

        def removeNotPresentRules(rule: dict):
            nonlocal hasPresentRule

            for x in [*rule.keys()]:
                if x == "required":
                    hasPresentRule = True
                if x not in [
                    "required",
                    "properties",
                    "dependentRequired",
                    "allOf",
                    "anyOf",
                    "oneOf",
                    "if",
                    "then",
                    "else",
                ]:
                    del rule[x]

            if "properties" in rule.keys():
                for x, v in rule["properties"].items():
                    rule["properties"][x] = removeNotPresentRules(v)

            for x in ["allOf", "anyOf", "oneOf"]:
                if x in rule:
                    for xx, vv in enumerate(rule[x]):
                        rule[x][xx] = removeNotPresentRules(vv)

            for x in ["then", "else"]:
                if x in rule:
                    rule[x] = removeNotPresentRules(rule[x])

            return rule

        removeNotPresentRules(rule)

        if hasPresentRule:
            return rule

        return None

    @staticmethod
    def getDependencyKeysInRule(rule):
        deps = []

        def findDependencies(obj, deps: list):
            for k, v in obj.items():
                if type(v) == dict:
                    findDependencies(v, deps)
                elif type(v) == str:
                    for x in [*re.finditer(r"\{\{\s*(.+)\s*\}\}", v)]:
                        deps.append(x[1])
                elif type(v) == list:
                    for vv in v:
                        for x in [*re.finditer(r"\{\{\s*(.+)\s*\}\}", vv)]:
                            deps.append(x[1])
            return deps

        return findDependencies(rule, deps)

    @staticmethod
    def getValidationErrorTemplateMessages():
        return {"required": "'{property}' is required"}

    @staticmethod
    def getValidationErrors(data: dict, ruleLists: dict, names: dict, messages: dict):
        errors = {}

        def replaceDependencies(obj, deps: list):
            for k, v in obj.items():
                if type(v) == dict:
                    replaceDependencies(v, deps)
                elif type(v) == str:
                    obj[k] = re.sub(
                        r"\{\{\s*(.+)\s*\}\}",
                        r"\1",
                    )
                elif type(v) == list:
                    for vv in v:
                        replaceDependencies(vv, deps)

        for k, ruleList in ruleLists.items():
            for rule in ruleList:
                for error in getValidator(rule).iter_errors(data):
                    if k not in errors:
                        errors[k] = []
                    requiredMsgMatch = re.match(
                        "'(.+)' is a required property",
                        error.message,
                    )
                    if requiredMsgMatch:
                        mainKey = [*error.path, requiredMsgMatch[1]][0]
                        subKey = "][".join([*error.path, requiredMsgMatch[1]][1:])
                        name = re.sub(
                            r"\[\.\.\.\]",
                            "[" + subKey + "]" if subKey else "",
                            names[mainKey],
                        )
                        error.message = re.sub(
                            r"\{property\}",
                            name,
                            messages["required"],
                        )
                    errors[k].append(error.message)

        return errors

    @staticmethod
    def hasArrayObjectRuleInRuleList(ruleList, key):
        has = False
        for rule in ruleList:
            keySegs = key.split(".")
            value = rule
            while keySegs:
                seg = keySegs.pop(0)
                if "properties" not in value:
                    break
                if seg not in value["properties"]:
                    break
                if not keySegs and "type" not in value["properties"][seg]:
                    break
                if not keySegs and value["properties"][seg]["type"] == "object":
                    has = True
                value = value["properties"][seg]
        return has

    @staticmethod
    def getResponseBody(result, totalErrors):
        if totalErrors:
            return {"errors": totalErrors}

        return {"result": result}
