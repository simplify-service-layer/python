import ast
import copy
import inspect
import json
import os
import re
import types
from abc import ABC, abstractmethod
from importlib.machinery import SourceFileLoader
from typing import Any, Callable, Dict, List, Type

from typing_extensions import Self


class ServiceBase(ABC):
    BIND_NAME_EXP = r"\{\{([a-zA-Z][\w\.\*]+)\}\}"
    __onFailCallbacks: List[Callable] = []
    __onStartCallbacks: List[Callable] = []
    __onSuccessCallbacks: List[Callable] = []
    __childs: Dict[str, Type[Self]] = {}
    __data: Dict[str, Any] = {}
    __errors: Dict[str, List[str]] = {}
    __inputs: Dict[str, Any] = {}
    __isRun: bool = False
    __names: Dict[str, str] = {}
    __parent: Self | None = None
    __validations: Dict[str, bool] = {}

    @staticmethod
    @abstractmethod
    def filterPresentRelatedRule(rule):
        pass

    @staticmethod
    @abstractmethod
    def getDependencyKeysInRule(rule):
        pass

    @staticmethod
    @abstractmethod
    def getValidationErrorTemplateMessages():
        pass

    @staticmethod
    @abstractmethod
    def getValidationErrors(data, ruleLists, names, messages):
        pass

    @staticmethod
    @abstractmethod
    def hasArrayObjectRuleInRuleList(ruleList, key=None):
        pass

    @staticmethod
    @abstractmethod
    def getResponseBody(result, totalErrors):
        pass

    @classmethod
    def __get_defined_functions(self, method):
        filepath = os.path.abspath(inspect.getfile(self))
        module_loader = SourceFileLoader("service_module", filepath)
        module = module_loader.exec_module(types.ModuleType(module_loader.name))
        namespace = {x: getattr(module, x) for x in dir(module)}
        before_namespace = copy.copy(namespace)
        function_code = inspect.getsource(getattr(self, method).__code__)
        indent = re.match(r"^\s*", function_code)[0]
        function_code = re.sub(r"^\s+", "", function_code)
        function_code = re.sub(r"\n" + indent, "\n", function_code)
        parsed = ast.parse(function_code)
        exec(ast.unparse(parsed.body[0].body), namespace)
        namespace = dict(
            filter(
                lambda x: x[0] not in before_namespace
                or x[1] != before_namespace[x[0]],
                namespace.items(),
            )
        )
        namespace = dict(
            filter(
                lambda x: x[0] not in ["__builtins__"],
                namespace.items(),
            )
        )

        return namespace

    @classmethod
    def addOnFailCallback(self, callback):
        self.__onFailCallbacks.append(callback)

    @classmethod
    def addOnStartCallback(self, callback):
        self.__onStartCallbacks.append(callback)

    @classmethod
    def addOnSuccessCallback(self, callback):
        self.__onSuccessCallbacks.append(callback)

    @classmethod
    def getAllBindNames(self):
        arr = {}
        for cls in [*self.getAllTraits(), self]:
            bindNames = cls.getBindNames()
            arr.update(bindNames)
            for k, v in bindNames.items():
                if len(k.split(".")) > 1:
                    raise Exception(
                        'including "." nested key '
                        + k
                        + " cannot be existed in "
                        + self.__name__
                    )

        return arr

    @classmethod
    def getAllCallbacks(self):
        arr = {}
        for cls in self.getTraits():
            for key, callback in cls.getAllCallbacks().items():
                if key in arr.keys():
                    raise Exception(
                        key
                        + " callback key is duplicated in traits in "
                        + self.__name__
                    )
                arr[key] = callback

        for key, callback in self.__get_defined_functions("getCallbacks").items():
            if not re.match(r"^[a-zA-Z][\w-]{0,}__[\w-]{1,}(|@defer)", key):
                raise Exception(
                    key + " callback key is not support pattern in " + self.__name__
                )
            arr[key] = callback

        return arr

    @classmethod
    def getAllLoaders(self):
        arr = {}
        for cls in self.getTraits():
            for key, loader in cls.getAllLoaders().items():
                if key in arr.keys():
                    raise Exception(
                        key + " loader key is duplicated in traits in " + cls.__name__
                    )
                arr[key] = loader

        for key, loader in self.__get_defined_functions("getLoaders").items():
            if not re.match(r"^[a-zA-Z][\w-]{0,}", key):
                raise Exception(
                    key + " loader key is not support pattern in " + self.__name__
                )
            arr[key] = loader

        return arr

    @classmethod
    def getAllPromiseLists(self):
        arr = {}

        for cls in [*self.getAllTraits(), self]:
            for key, promiseList in cls.getPromiseLists().items():
                if key not in arr.keys():
                    arr[key] = []
                for promise in promiseList:
                    if promise not in arr[key]:
                        arr[key].append(promise)

        return arr

    @classmethod
    def getAllRuleLists(self):
        arr = {}

        for cls in [*self.getAllTraits(), self]:
            arr[cls] = {}
            for key, ruleList in cls.getRuleLists().items():
                if not isinstance(ruleList, list):
                    ruleList = [ruleList]
                if key not in arr[cls].keys():
                    arr[cls][key] = []
                for rule in ruleList:
                    arr[cls][key].append(rule)

        return arr

    @classmethod
    def getAllTraits(self) -> List[Self]:
        arr = []

        for cls in self.getTraits():
            if ServiceBase not in cls.__bases__:
                raise Exception("trait class must extends Service")
            arr = [*arr, *cls.getAllTraits()]

        arr = [*arr, *self.getTraits()]
        arr = list(set(arr))

        return arr

    @staticmethod
    def getBindNames():
        return {}

    @staticmethod
    def getCallbacks():
        pass

    @staticmethod
    def getLoaders():
        pass

    @staticmethod
    def getPromiseLists():
        return {}

    @staticmethod
    def getRuleLists():
        return {}

    @staticmethod
    def getTraits():
        return []

    @staticmethod
    def initService(value):
        if len(value) < 2:
            value[1] = {}
        if len(value) < 3:
            value[2] = {}

        cls = value[0]
        data = value[1]
        names = value[2]

        for key, value in data:
            if "" == value:
                del data[key]

        return cls().setWith(data, names)

    @classmethod
    def isInitable(self, value):
        return (
            isinstance(value, list)
            and len(value) != 0
            and self.isServiceClass(value[0])
        )

    @classmethod
    def isServiceClass(self, value):
        if not isinstance(value, type):
            return False

        isService = False
        for x in value.__bases__:
            if x == ServiceBase:
                isService = True
            elif x != object:
                isService = self.isServiceClass(x)
        return isService

    def getChilds(self):
        return copy.deepcopy(self.__childs)

    def getData(self):
        return copy.deepcopy(self.__data)

    def getErrors(self):
        return copy.deepcopy(self.__errors)

    def getInjectedPropNames(self):
        injectedPropNames = []

        for k in vars(self).keys():
            if k.startswith("_" + self.__class__.__name__ + "__"):
                injectedPropNames.append(
                    re.sub(r"^_" + self.__class__.__name__ + "__", "__", k)
                )
            else:
                injectedPropNames.append(k)
        return injectedPropNames

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

    def resolveBindName(self, name):
        while True:
            boundKeys = self.__getBindKeysInName(name)
            if not boundKeys:
                break

            key = boundKeys[0]
            keySegs = key.split(".")
            mainKey = keySegs[0]
            bindNames = copy.deepcopy(self.getAllBindNames())
            bindNames.update(self.__names)

            if mainKey in bindNames:
                bindName = bindNames[mainKey]
            else:
                raise Exception(
                    '"' + mainKey + '" name not exists in ' + self.__class__.__name__,
                )

            pattern = r"\{\{(\s*)" + key + r"(\s*)\}\}"
            replace = self.resolveBindName(bindName)
            name = re.sub(pattern, replace, name)
            matches = re.findall(r"\[\.\.\.\]", name)

            if len(matches) > 1:
                raise Exception(
                    name + ' has multiple "[...]" string in ' + self.__class__.__name__
                )
            if self.__hasArrayObjectRuleInRuleLists(mainKey) and not matches:
                raise Exception(
                    '"'
                    + mainKey
                    + '" name is required "[...]" string in '
                    + self.__class__.__name__
                )

            if len(keySegs) > 1:
                replace = "[" + "][".join(keySegs[1:]) + "]"
                name = re.sub(r"\[\.\.\.\]", replace, name)

        return name

    def run(self):
        if self.__isRun:
            raise Exception("already run service [" + self.__class__.__name__ + "]")

        self.__childs = {}
        self.__data = {}
        self.__errors = {}
        self.__validations = {}

        totalErrors = self.getTotalErrors()

        if not self.__isRun:
            if not self.__parent:
                for callback in self.__onStartCallbacks:
                    callback()
            else:
                for key in self.__names.keys():
                    self.__names[key] = self.__parent.resolveBindName(self.__names[key])

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

        if self.__parent:
            if totalErrors:
                return self.__resolveError()

            return self.getData()["result"]

        result = self.getData()["result"] if "result" in self.getData().keys() else None

        return self.getResponseBody(result, totalErrors)

    def setParent(self, parent):
        self.__parent = parent

    def setWith(
        self,
        inputs: Dict[str, Any] = {},
        names: Dict[str, str] = {},
    ):
        if self.__isRun:
            raise Exception("already run service [" + self.__class__.__name__ + "]")

        for key in inputs.keys():
            if key in self.getInjectedPropNames():
                raise Exception(
                    key
                    + " input key is duplicated with property in "
                    + self.__class__.__name__
                )

            if not re.match(r"^[a-zA-Z][\w-]{0,}", key):
                raise Exception(
                    key
                    + " input key is not support pattern in "
                    + self.__class__.__name__
                )

        for key in inputs.keys():
            if key in self.__inputs.keys():
                raise Exception(
                    key + " input key is duplicated in " + self.__class__.__name__
                )

        for key in names.keys():
            if key in self.__names.keys():
                raise Exception(
                    key + " name key is duplicated in " + self.__class__.__name__
                )

        for key in inputs.keys():
            if "" == inputs[key]:
                del inputs[key]

        self.__inputs = self.__inputs | inputs
        self.__names = self.__names | names

        self.getAllCallbacks()
        self.getAllLoaders()

        return self._clone()

    def _clone(self):
        return copy.copy(self)

    def __filterAvailableExpandedRuleLists(self, cls, data, ruleLists):

        for k in ruleLists.keys():
            keySegs = k.split(".")
            for i in range(len(keySegs) - 1):
                parentKey = ".".join(keySegs[0 : i + 1])
                hasArrayObjectRule = self.__hasArrayObjectRuleInRuleLists(parentKey)
                if not hasArrayObjectRule:
                    raise Exception(
                        parentKey + " key must has array rule in " + cls.__name__
                    )

        i = 0
        while True:
            i = i + 1
            filteredRuleLists = dict(
                filter(
                    lambda k: re.match(r"\.\*$", k[0]) or re.match(r"\.\*\.", k[0]),
                    ruleLists.items(),
                )
            )

            if len(filteredRuleLists) == 0:
                break

            for rKey in filteredRuleLists.keys():
                matches = re.match(r"^(.+?)\.\*", rKey)
                allSegs = (matches[1] + ".*").split(".")
                segs = []
                rKeyVal = dict(data)
                isLastKeyExists = True

                while allSegs:
                    seg = allSegs.pop(0)
                    segs.append(seg)
                    k = ".".join(segs)

                    if not isinstance(rKeyVal, dict) or (
                        len(allSegs) != 0 and seg not in rKeyVal
                    ):
                        isLastKeyExists = False

                        break

                    if len(allSegs) != 0:
                        rKeyVal = rKeyVal[seg]

                if isLastKeyExists:
                    for k, v in rKeyVal:
                        rNewKey = re.sub(
                            r"^" + matches[1] + r"\.\*", matches[1] + r"." + k, rKey
                        )
                        ruleLists[rNewKey] = ruleLists[rKey]

                del ruleLists[rKey]

        for rKey in ruleLists.keys():
            allSegs = rKey.split(".")
            segs = []
            rKeyVal = dict(data)
            while allSegs:
                seg = allSegs.pop(0)
                segs.append(seg)
                k = ".".join(segs)

                if k not in ruleLists:
                    break

                if isinstance(rKeyVal, dict) and seg not in rKeyVal.keys():
                    ruleLists[k] = list(
                        filter(
                            lambda rule: cls.filterPresentRelatedRule(rule),
                            ruleLists[k],
                        )
                    )

                if not isinstance(rKeyVal, dict) or (
                    len(allSegs) != 0 and seg not in rKeyVal
                ):
                    removeRuleLists = dict(
                        filter(
                            lambda v: re.match(r"^" + k + r"\.", v[0]),
                            ruleLists.items(),
                        )
                    )

                    for v in removeRuleLists.keys():
                        del ruleLists[v]

                    break

                if len(allSegs) != 0:
                    rKeyVal = rKeyVal[seg]

        return ruleLists

    def __getBindKeysInName(self, str):
        return re.findall(self.BIND_NAME_EXP, str)

    def __getClosureDependencies(self, func, excludeProps=True):
        deps = []
        params = inspect.signature(func).parameters
        props = self.getInjectedPropNames()

        for key in params.keys():
            if excludeProps:
                if not key in props:
                    deps.append(key)
            else:
                deps.append(key)

        return deps

    def __getLoadedDataWith(self, key):
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
        hasResolveError = False

        for i, v in enumerate(values):
            service = None

            if self.isInitable(v):
                if len(v) < 2:
                    v.append({})
                if len(v) < 3:
                    v.append({})

                for k, name in v[2].items():
                    v[2][k] = self.resolveBindName(name)

                service = self.initService(v)
                service.setParent(self)
                resolved = service.run()
            elif isinstance(v, ServiceBase):
                service = v
                service.setParent(self)
                resolved = service.run()

            if service:
                if hasServicesInArray:
                    self.__childs[key + "." + str(i)] = service
                else:
                    self.__childs[key] = service

                if self.__isResolveError(resolved):
                    del values[i]
                    hasResolveError = True
                    self.__validations[key] = False
                values[i] = resolved

        if not hasResolveError:
            self.__data[key] = values if hasServicesInArray else values[0]

        return self.__data

    def __getOrderedCallbackKeys(self, key):
        promiseKeys = list(
            filter(
                lambda value: re.match("^" + key + "__", value),
                self.getAllPromiseLists().keys(),
            )
        )
        allKeys = list(
            filter(
                lambda value: re.match("^" + key + "__", value),
                self.getAllCallbacks().keys(),
            )
        )
        orderedKeys = self.__getShouldOrderedCallbackKeys(promiseKeys)
        restKeys = list(set(allKeys) - set(orderedKeys))

        return [*orderedKeys, *restKeys]

    def __getRelatedRuleLists(self, key, cls):
        ruleLists = (
            self.getAllRuleLists()[cls] if cls in self.getAllRuleLists().keys() else {}
        )

        filterLists = dict(
            filter(
                lambda k: re.match(r"^" + key + "$", k[0])
                or re.match(r"^" + key + r"\.", k[0]),
                ruleLists.items(),
            )
        )
        keySegs = key.split(".")

        for i in range(len(keySegs) - 1):
            parentKey = ".".join(keySegs[0 : i + 1])
            if parentKey in ruleLists.keys():
                filterLists[parentKey] = ruleLists[parentKey]

        return filterLists

    def __getShouldOrderedCallbackKeys(self, keys):
        arr = []

        for key in keys:
            promiseLists = self.getAllPromiseLists()
            deps = promiseLists[key] if key in promiseLists else []
            orderedKeys = self.__getShouldOrderedCallbackKeys(deps)
            arr = [*orderedKeys, key, *arr]

        return list(set(arr))

    def __hasArrayObjectRuleInRuleLists(self, key):
        hasArrayObjectRule = False
        for cls, ruleLists in self.getAllRuleLists().items():
            ruleList = ruleLists[key] if key in ruleLists else []
            if cls.hasArrayObjectRuleInRuleList(ruleList, key):
                hasArrayObjectRule = True
        return hasArrayObjectRule

    def __isResolveError(self, value):
        errorClass = self.__resolveError().__class__

        return isinstance(value, errorClass)

    def __resolve(self, func):
        props = self.getInjectedPropNames()
        depNames = self.__getClosureDependencies(func, False)
        depVals = []
        params = {}

        for key, param in inspect.signature(func).parameters.items():
            params[key] = param

        for i, depName in enumerate(depNames):
            if depName in props:
                depVals.append(getattr(self, depName))
            elif self.__validations[depName] and depName in self.__data.keys():
                depVals.append(self.__data[depName])
            elif (
                self.__validations[depName]
                and params[depName].default != inspect.Parameter.empty
            ):
                depVals.append(params[depName].default)
            else:
                return self.__resolveError()

        return func(*depVals)

    def __resolveError(self):
        return Exception("can't be resolve")

    def __runAllDeferCallbacks(self):
        callbacks = list(
            filter(
                lambda key: re.match("/:defer$/", key[0]),
                self.getAllCallbacks().items(),
            )
        )

        for callback in callbacks:
            self.__resolve(callback)

        for child in self.__childs.values():
            child.__runAllDeferCallbacks()

    def __validate(self, key, depth=""):
        depth = depth if depth + "|" + key else key
        depths = depth.split("|")
        mainKey = key.split(".")[0]

        if key in self.__validations:
            return self.__validations[key]

        if len(list(filter(lambda seg: seg == key, depths))) >= 2:
            raise Exception(
                "validation dependency circular reference["
                + depth
                + "] occurred in "
                + self.__class__.__name__,
            )

        keySegs = key.split(".")

        for i in range(len(keySegs) - 1):
            parentKey = ".".join(keySegs[0 : i + 1])
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
        items = json.loads(json.dumps(data, default=vars))

        self.__validateWith(key, items, depth)

        # unnecessary because data is stored already.
        if key in data.keys():
            self.__data[key] = data[key]

        orderedCallbackKeys = self.__getOrderedCallbackKeys(key)
        callbacks = self.getAllCallbacks()

        for callbackKey in orderedCallbackKeys:
            callback = self.getAllCallbacks()[callbackKey]
            deps = self.__getClosureDependencies(callback)

            for dep in deps:
                if not self.__validate(dep, depth):
                    self.__validations[key] = False

        if True == self.__validations[key]:
            for callbackKey in orderedCallbackKeys:
                if not re.match("@defer$", callbackKey):
                    callback = callbacks[callbackKey]
                    self.__resolve(callback)

        if False == self.__validations[key]:
            return False

        return True

    def __validateWith(self, key, items, depth):
        mainKey = key.split(".")[0]

        for cls in [*self.getAllTraits(), self.__class__]:
            names = dict()
            ruleLists = self.__getRelatedRuleLists(key, cls)
            ruleLists = self.__filterAvailableExpandedRuleLists(
                cls,
                items,
                ruleLists,
            )

            for k, ruleList in ruleLists.items():
                for j, rule in enumerate(ruleList):
                    depKeysInRule = cls.getDependencyKeysInRule(rule)
                    for depKey in depKeysInRule:
                        if re.match(r"\.\*", depKey):
                            raise Exception(
                                "wildcard(*) key can't exists in rule dependency in "
                                + cls.__name__
                            )

                        depKeySegs = depKey.split(".")
                        depVal = dict(items)
                        hasDepVal = True
                        while not depKeySegs:
                            seg = depKeySegs.pop(0)
                            if seg not in depVal:
                                hasDepVal = False

                                break

                            depVal = depVal[seg]

                        if not hasDepVal:
                            del ruleLists[k][j]

                        if not self.__validate(depKey, depth):
                            self.__validations[key] = False
                            del ruleLists[k][j]

                        names[depKey] = self.resolveBindName("{{" + depKey + "}}")

            for k, ruleList in ruleLists.items():
                if ruleList:
                    names[k] = self.resolveBindName("{{" + k + "}}")

            messages = self.getValidationErrorTemplateMessages()

            for ruleKey, ruleList in ruleLists.items():
                errorLists = self.getValidationErrors(
                    items,
                    {(ruleKey): ruleList},
                    names,
                    messages,
                )

                if errorLists:
                    if ruleKey not in self.__errors:
                        self.__errors[ruleKey] = []

                    for error in errorLists[ruleKey]:
                        if error not in self.__errors[ruleKey]:
                            self.__errors[ruleKey].append(error)

                    self.__validations[key] = False
                    return False

        if key in self.__validations and False == self.__validations[key]:
            return False

        self.__validations[key] = True

        return True
