import ast
import copy
import inspect
import json
import os
import re
from abc import *
from importlib.machinery import SourceFileLoader
from typing import Any, Callable, Null, Self


class ServiceBase(metaclass=ABCMeta):
    BIND_NAME_EXP = r"\{\{([a-zA-Z][\w\.\*]+)\}\}"
    __onFailCallbacks: list[Callable] = []
    __onStartCallbacks: list[Callable] = []
    __onSuccessCallbacks: list[Callable] = []
    __childs: dict[str, Self]
    __data: dict[str, Any]
    __errors: dict[str, list[str]]
    __inputs: dict[str, Any]
    __isRun: bool
    __names: dict[str, str]
    __parent: Self | None
    __validations: dict[str, bool]

    @abstractmethod
    @staticmethod
    def filterPresentRelatedRule(rule):
        pass

    @abstractmethod
    @staticmethod
    def getDependencyKeysInRule(rule):
        pass

    @abstractmethod
    @staticmethod
    def getValidationErrorTemplateMessages():
        pass

    @abstractmethod
    @staticmethod
    def getValidationErrors(data, ruleLists, names, messages):
        pass

    @abstractmethod
    @staticmethod
    def hasArrayObjectRuleInRuleList(ruleList):
        pass

    @abstractmethod
    @staticmethod
    def removeDependencyKeySymbolInRule(rule):
        pass

    @abstractmethod
    @staticmethod
    def getResponseBody(result, totalErrors):
        pass

    def __init__(
        self,
        inputs: dict[str, Any] = {},
        names: dict[str, str] = {},
        parent: Self | None = None,
    ):
        self.__childs = {}
        self.__data = {}
        self.__errors = {}
        self.__inputs = inputs
        self.__names = names
        self.__validations = {}
        self.__isRun = False
        self.__parent = parent

        for key in self.__inputs.keys():
            if not re.match(r"^[a-zA-Z][\w-]{0,}", key):
                raise Exception(
                    key + " loader key is not support pattern in " + type(self).__name__
                )

        for key in self.__inputs.keys():
            self.__validate(key)

        type(self).getAllCallbacks()
        type(self).getAllLoaders()

    @classmethod
    def addOnFailCallback(cls, callback):
        cls.__onFailCallbacks.append(callback)

    @classmethod
    def addOnStartCallback(cls, callback):
        cls.__onStartCallbacks.append(callback)

    @classmethod
    def addOnSuccessCallback(cls, callback):
        cls.__onSuccessCallbacks.append(callback)

    @classmethod
    def getAllBindNames(cls):
        arr = {}
        for cl in [*cls.getAllTraits(), cls]:
            arr.update(cl.getBindNames())

        return arr

    @classmethod
    def getAllCallbacks(cls):
        arr = {}

        for key in cls.getCallbacks().keys():
            if not re.match(r"^[a-zA-Z][\w-]{0,}#[\w-]{1,}(|@defer)", key):
                raise Exception(
                    key + " callback key is not support pattern in " + cls.__name__
                )

        for cl in cls.getTraits():
            for key, callback in cl.getAllCallbacks().items():
                if key in arr.keys():
                    raise Exception(
                        key + " callback key is duplicated in traits in " + cls.__name__
                    )
                arr[key] = callback

        arr.update(cls.getCallbacks())

        return arr

    @classmethod
    def getAllLoaders(cls):
        arr = {}

        for key in cls.getLoaders().keys():
            if not re.match(r"^[a-zA-Z][\w-]{0,}", key):
                raise Exception(
                    key + " loader key is not support pattern in " + cls.__name__
                )

        for cl in cls.getTraits():
            filepath = os.path.abspath(inspect.getfile(cl))
            module = SourceFileLoader("service_module", filepath).load_module()
            namespace = {x: getattr(module, x) for x in dir(module)}
            before_namespace = copy.copy(namespace)
            function_code = inspect.getsource(cl.getAllLoaders.__code__)
            parsed = ast.parse(re.sub("^\s+", "", function_code))
            exec(ast.unparse(parsed.body[0].body), namespace)
            namespace = dict(
                filter(
                    lambda x: x[0] not in before_namespace
                    or x[1] != before_namespace[x[0]],
                    namespace.items(),
                )
            )
            for key, loader in namespace.items():
                if key in arr.keys():
                    raise Exception(
                        key + " loader key is duplicated in traits in " + cls.__name__
                    )
                arr[key] = loader

        arr.update(cls.getLoaders())

        return arr

    @classmethod
    def getAllPromiseLists(cls):
        arr = {}

        for cl in [*cls.getAllTraits(), cls]:
            for key, promiseList in cl.getPromiseLists().items():
                if key not in arr.keys():
                    arr[key] = []
                for promise in promiseList:
                    if promise not in arr[key]:
                        arr[key].append(promise)

        return arr

    @classmethod
    def getAllRuleLists(cls):
        arr = {}

        for cl in [*cls.getAllTraits(), cls]:
            arr[cl] = {}
            for key, ruleList in cl.getRuleLists().items():
                if not isinstance(ruleList, list):
                    ruleList = [ruleList]
                if key not in arr[cl].keys():
                    arr[cl][key] = []
                for rule in ruleList:
                    arr[cl][key].append(rule)

        return arr

    @classmethod
    def getAllTraits(cls) -> list[Self]:
        arr = []

        for cl in cls.getTraits():
            if ServiceBase not in cl.__bases__:
                raise Exception("trait class must extends Service")
            arr = [*arr, *cl.getAllTraits()]

        arr = [*arr, *cls.getTraits()]
        arr = list(set(arr))

        return arr

    @classmethod
    def getBindNames(cls):
        return {}

    @classmethod
    def getCallbacks(cls):
        return {}

    @classmethod
    def getLoaders(cls):
        return {}

    @classmethod
    def getPromiseLists(cls):
        return {}

    @classmethod
    def getRuleLists(cls):
        return {}

    @classmethod
    def getTraits(cls):
        return []

    def initService(value):
        value[1] = {} if not value[1] else None
        value[2] = {} if not value[2] else None
        value[3] = None if not value[3] else None

        cls = value[0]
        data = value[1]
        names = value[2]
        parent = value[3]

        for key, value in data:
            if "" == value:
                del data[key]

        return cls(data, names, parent)

    def isInitable(value):
        return (
            isinstance(value, list)
            and len(value) != 0
            and isinstance(value[0], type)
            and ServiceBase in value[0].__bases__
        )

    def getChilds(self):
        return copy.deepcopy(self.__childs)

    def getData(self):
        return copy.deepcopy(self.__data)

    def getErrors(self):
        return copy.deepcopy(self.__errors)

    def getInputs(self):
        return copy.deepcopy(self.__inputs)

    def getNames(self):
        return copy.deepcopy(self.__names)

    def getTotalErrors(self):
        errors = self.getErrors()

        for key, child in self.getChilds().items():
            childErrors = child.getTotalErrors()
            if childErrors:
                errors[key] = childErrors

        return errors

    def getValidations(self):
        return copy.deepcopy(self.__validations)

    def run(self):
        totalErrors = self.getTotalErrors()

        if not self.__isRun:
            if not self.__parent:
                for callback in self.__onStartCallbacks:
                    callback()

            for key in self.getInputs().keys():
                self.__validate(key)

            for cls in self.getAllRuleLists().keys():
                for key in self.getAllRuleLists()[cls].keys():
                    self.__validate(key)

            for key in self.getAllLoaders().keys():
                self.__validate(key)

            totalErrors = self.getTotalErrors()

            if not self.__parent:
                if not totalErrors:
                    self.__runAllDeferCallbacks()
                    for callback in self.__onSuccessCallbacks:
                        callback()
                else:
                    for callback in self.__onFailCallbacks:
                        callback()

            self.__isRun = True

        if not totalErrors and "result" not in self.getData().keys():
            raise Exception("result data key is not exists in " + type(self).__name__)

        if self.__parent:
            if totalErrors:
                return self.__resolveError()

            return self.getData()["result"]

        result = self.getData()["result"] if "result" in self.getData().keys() else None

        return self.getResponseBody(result, totalErrors)

    def __filterAvailableExpandedRuleLists(self, cls, key, data, ruleLists):

        for k in ruleLists.keys():
            segs = k.split(".")
            for i in range(len(segs) - 1):
                hasArrayObjectRule = False
                parentKey = ".".join(segs[0, i + 1])
                for cl, parentRuleLists in self.getAllRuleLists().items():
                    parentRuleList = (
                        parentRuleLists[parentKey]
                        if parentKey in parentRuleLists
                        else []
                    )
                    if cl.hasArrayObjectRuleInRuleList(parentRuleList):
                        hasArrayObjectRule = True

                if not hasArrayObjectRule:
                    raise Exception(
                        parentKey + " key must has array rule in " + type(self).__name__
                    )

        i = 0
        while True:
            i = i + 1
            filteredRuleLists = filter(
                lambda k: re.match(r"\.\*$", k) or re.match(r"\.\*\.", k), ruleLists
            )

            if len(filteredRuleLists) == 0:
                break

            for rKey in filteredRuleLists.keys():
                matches = re.match(r"^(.+?)\.\*", rKey)
                allSegs = (matches[1] + ".*").split(".")
                segs = []
                rKeyVal = data
                isSuccess = True

                while allSegs:
                    seg = allSegs.pop(0)
                    segs.append(seg)
                    k = ".".join(segs)

                    if not isinstance(rKeyVal, list) or (
                        len(allSegs) != 0 and seg not in rKeyVal
                    ):
                        isSuccess = False

                        break

                    if len(allSegs) != 0:
                        rKeyVal = rKeyVal[seg]

                if isSuccess:
                    for k, v in rKeyVal:
                        rNewKey = re.sub(
                            "^" + allSegs + "\.\*", allSegs + "." + k, rKey
                        )
                        ruleLists[rNewKey] = ruleLists[rKey]
                        self.__names[rNewKey] = re.sub(
                            r"\{\{(\s*)" + i + r"(\s*)\}\}",
                            k,
                            self.__resolveBindName("{{" + rKey + "}}"),
                        )

                    del ruleLists[rKey]
                    del self.__names[rKey]

        for rKey in ruleLists.keys():
            allSegs = rKey.split(".")
            segs = []
            rKeyVal = data
            while allSegs:
                seg = allSegs.pop(0)
                segs.append(seg)
                k = ".".join(segs)

                if k not in ruleLists:
                    break

                if isinstance(rKeyVal, list) and seg not in rKeyVal.keys():
                    ruleLists[k] = filter(
                        lambda rule: cls.filterPresentRelatedRule(rule), ruleLists[k]
                    )

                if not isinstance(rKeyVal, list) or (
                    len(allSegs) != 0 and seg not in rKeyVal
                ):
                    self.__validations[key] == False
                    removeRuleLists = list(
                        filter(lambda v: re.match(r"^" + k + "\.", v), ruleLists)
                    )

                    for v in removeRuleLists.keys():
                        del ruleLists[v]

                    removeNames = list(
                        filter(lambda v: re.match(r"^" + k + "\.", v), self.__names)
                    )

                    for v in removeNames.keys():
                        del self.__names[v]

                    break

                if len(allSegs) != 0:
                    rKeyVal = rKeyVal[seg]

        return ruleLists

    def __getBindKeysInName(self, str):
        return re.findall(self.BIND_NAME_EXP, str)

    def __getClosureDependencies(self, func):
        arr = []
        sig = inspect.signature(func)

        for key in sig.parameters.keys():
            arr.append(key)

        return arr

    def __getLoadedDataWith(self, key):
        # let hasServicesInArray, hasError, values
        data = self.getData()
        loader = (
            self.getAllLoaders()[key] if key in self.getAllLoaders().keys() else None
        )

        if key in data.keys():
            return data

        if key in self.getInputs().keys():
            value = self.getInputs()[key]
        else:
            if not loader:
                return data
            value = self.__resolve(loader)

        if self.__isResolveError(value):
            return data

        hasServicesInArray = False

        if value and isinstance(value, list):
            for v in value:
                if self.isInitable(v):
                    hasServicesInArray = True

        values = value if hasServicesInArray else [value]
        hasError = False

        for i, v in enumerate(values):
            if self.isInitable(v):
                v[1] = {} if len(v) >= 2 and not v[1] else None
                v[2] = {} if len(v) >= 3 and not v[2] else None
                for k, name in v[2].items():
                    v[2][k] = self.__resolveBindName(name)
                v[3] = self
                service = self.initService(v)
                resolved = service.run()
            elif isinstance(v, ServiceBase):
                service = v
                resolved = service.run()

            if service:
                self.__childs[key + "." + i if hasServicesInArray else key] = service
                if self.__isResolveError(resolved):
                    del values[i]
                    hasError = True
                    self.__validations[key] = False
                values[i] = resolved

        if not hasError:
            self.__data[key] = values if hasServicesInArray else values[0]

        return self.__data

    def __getOrderedCallbackKeys(self, key):
        promiseKeys = filter(
            lambda value: re.match("^" + key + "#", value),
            self.getAllPromiseLists().keys(),
        )
        allKeys = filter(
            lambda value: re.match("^" + key + "#", value),
            self.getAllCallbacks().keys(),
        )
        orderedKeys = self.__getShouldOrderedCallbackKeys(promiseKeys)
        restKeys = list(set(allKeys) - set(orderedKeys))

        return [*orderedKeys, *restKeys]

    def __getRelatedRuleLists(self, key, cls):
        ruleLists = (
            self.getAllRuleLists()[cls] if cls in self.getAllRuleLists().keys() else {}
        )

        return filter(
            lambda k: re.match(r"^" + key + "$", k) or re.match(r"^" + key + "\.", k),
            ruleLists,
        )

    def __getShouldOrderedCallbackKeys(self, keys):
        arr = []

        for key in keys:
            promiseLists = self.getAllPromiseLists()
            deps = promiseLists[key] if key in promiseLists else []
            list = self.__getShouldOrderedCallbackKeys(deps)
            arr = [*list, key, *arr]

        return list(set(arr))

    def __isResolveError(self, value):
        errorClass = type(self.__resolveError())

        return isinstance(value, errorClass)

    def __resolve(self, func):
        sig = inspect.signature(func)
        depNames = self.__getClosureDependencies(func)
        depVals = []
        params = {}

        for key, param in sig.parameters.items():
            params[key] = param.default

        for i, depName in enumerate(depNames):
            if self.__validations[depName] and depName in self.__data.keys():
                depVals.append(self.__data[depName])
            elif self.__validations[depName] and params[i] != inspect.Parameter.empty:
                depVals.append(params[i])
            else:
                return self.__resolveError()

        return func(*depVals)

    def __resolveBindName(self, name):
        while True:
            boundKeys = self.__getBindKeysInName(name)
            if not boundKeys:
                break

            key = boundKeys[0]
            pattern = r"\{\{(\s*)" + key + r"(\s*)\}\}"
            bindNames = copy.deepcopy(self.getAllBindNames().items)
            bindNames.update(self.__names)

            if key in bindNames:
                bindName = bindNames[key]
            else:
                raise Exception(
                    '"' + key + '" name not exists in ' + type(self).__name__,
                )
            name = re.sub(pattern, self.__resolveBindName(bindName), name)

        return name

    def __resolveError(self):
        return Exception("can't be resolve")

    def __runAllDeferCallbacks(self):
        callbacks = filter(
            lambda key: re.match("/:defer$/", key), self.getAllCallbacks()
        )

        for callback in callbacks:
            self.__resolve(callback)

        for child in self.__childs:
            child.__runAllDeferCallbacks()

    def __validate(self, key, depth=""):
        depth = depth if depth + "|" + key else key
        depths = depth.split("|")
        mainKey = key.split(".")[0]

        if len(list(filter(lambda seg: seg == key, depths))) >= 2:
            raise Exception(
                "validation dependency circular reference["
                + depth
                + "] occurred in "
                + type(self).__name__,
            )

        if self.__validations[key]:
            return self.__validations[key]

        keySegs = key.split(".")

        for i in range(keySegs.length - 1):
            parentKey = ".".join(keySegs.slice(0, i + 1))
            if (
                parentKey in self.__validations.keys()
                and True == self.__validations[parentKey]
            ):
                self.__validations[key] = True
                return True

        promiseList = (
            self.getAllPromiseLists()[mainKey]
            if mainKey in self.getAllPromiseLists().keys()
            else []
        )

        for promise in promiseList:
            if not self.__validate(promise, depth):
                self.__validations[mainKey] = False
                return False

        loader = (
            self.getAllLoaders()[mainKey]
            if mainKey in self.getAllLoaders().keys()
            else None
        )
        deps = self.__getClosureDependencies(loader) if loader else []

        for dep in deps:
            if not self.__validate(dep, depth):
                self.__validations[mainKey] = False

        data = self.__getLoadedDataWith(mainKey)
        items = json.load(json.dumps(data))

        self.__validateWith(key, items, depth)

        # unnecessary because data is stored already.
        if key in data.keys():
            self.__data[key] = data[key]

        orderedCallbackKeys = self.__getOrderedCallbackKeys(key)

        for callbackKey in orderedCallbackKeys:
            callback = self.getAllCallbacks()[callbackKey]
            deps = self.__getClosureDependencies(callback)

            for dep in deps:
                if not self.__validate(dep, depth):
                    self.__validations[key] = False

            if not re.match("@defer$", callbackKey):
                self.__resolve(callback)

        if False == self.__validations[key]:
            return False

        return True

    def __validateWith(self, key, items, depth):
        for cls in [*self.getAllTraits(), type(self)]:
            ruleLists = self.__getRelatedRuleLists(key, cls)
            allDepKeysInRule = []
            notMustPresentDepKeysInRule = []
            mustPresentDepKeysInRule = []

            for ruleList in ruleLists.values():
                for rule in ruleList:
                    presentRelatedRule = self.filterPresentRelatedRule(rule)
                    if presentRelatedRule:
                        notMustPresentDepKeysInRule = [
                            *notMustPresentDepKeysInRule,
                            *self.getDependencyKeysInRule(presentRelatedRule),
                        ]

                    allDepKeysInRule = [
                        *allDepKeysInRule,
                        *self.getDependencyKeysInRule(rule),
                    ]

            mustPresentDepKeysInRule = list(
                set(allDepKeysInRule) - set(notMustPresentDepKeysInRule)
            )

            for k in list(set(allDepKeysInRule)):
                if re.match(r"\.\*", k):
                    raise Exception(
                        "wildcard(*) key can't exists in rule dependency in "
                        + type(self).__name__
                    )
                if not self.__validate(k, depth):
                    self.__validations[key] = False

            for k in list(set(mustPresentDepKeysInRule)):
                if k not in self.__data.keys():
                    raise Exception(
                        '"'
                        + k
                        + '" key required rule not exists in '
                        + type(self).__name__
                    )

            for k, ruleList in ruleLists.items():
                for j, rule in enumerate(ruleList):
                    ruleLists[k][j] = self.removeDependencyKeySymbolInRule(rule)

            ruleLists = self.filterAvailableExpandedRuleLists(
                cls,
                key,
                items,
                ruleLists,
            )

            messages = self.getValidationErrorTemplateMessages()
            names = {}

            for v, k in self.__names.items():
                names[k] = self.__resolveBindName(v)

            for ruleKey, ruleList in ruleLists:
                errorLists = self.getValidationErrors(
                    items,
                    {(ruleKey): ruleList},
                    names,
                    messages,
                )

                if errorLists:
                    if ruleKey not in self.__errors:
                        self.__errors[ruleKey] = []

                    self.__errors[ruleKey] = [
                        *self.__errors[ruleKey],
                        *errorLists[ruleKey],
                    ]
                    self.__validations[key] = False
                    return False

        if key in self.__validations and False == self.__validations[key]:
            return False

        self.__validations[key] = True

        return True
