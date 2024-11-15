import json
import os
import sys

sys.path.append(os.getcwd())

from src.service import Service


def test_load_data_from_input():

    class ParentService(Service):
        def getBindNames():
            return {"result": "name for key1"}

        def getCallbacks():
            pass

        def getLoaders():
            pass

        def getRuleLists():
            return {"result": {"required": ["result"]}}

    service = ParentService({"result": "result value"})
    service.run()

    assert service.getTotalErrors() == {}


def test_load_data_from_input_child_batch_service():
    class ChildService(Service):
        def getBindNames():
            return {}

        def getLoaders():
            def result():
                return "child result value"

    class ParentService(Service):
        def getBindNames():
            return {
                "result": "parent result name",
            }

        def getLoaders():
            def result():
                pass

        def getRuleLists():
            return {"result": {"required": ["result"]}}

    service = ParentService(
        {
            "result": [
                [ChildService],
                [ChildService],
            ]
        }
    )
    service.run()

    assert service.getTotalErrors() == {}
    assert service.getData()["result"] == [
        "child result value",
        "child result value",
    ]


def test_load_data_from_input_service():
    class ChildService(Service):
        def getLoaders():
            def result():
                return "child result value"

    class ParentService(Service):
        def getBindNames():
            return {
                "result": "parent result name",
            }

        def getRuleLists():
            return {"result": {"required": ["result"]}}

    service = ParentService({"result": [ChildService]})
    service.run()
    value = service.getData()["result"]

    assert value == "child result value"
    assert service.getTotalErrors() == {}


def test_load_data_from_loader():
    class Service1(Service):
        def getBindNames():
            return {
                "result": "name for result",
            }

        def getLoaders():
            def result():
                return "result value"

        def getRuleLists():
            return {
                "result": {
                    "required": ["result"],
                    "properties": {"result": {"type": "string"}},
                }
            }

    service1 = Service1()
    service1.run()

    assert service1.getTotalErrors() == {}

    class Service2(Service):
        def getBindNames():
            return {
                "result": "name for result",
            }

        def getLoaders():
            def result():
                return ["aaa", "bbb", "ccc"]

        def getRuleLists():
            return {
                "result": {
                    "required": ["result"],
                    "properties": {"result": {"type": "string"}},
                }
            }

    service2 = Service2()
    service2.run()

    assert service2.getTotalErrors() != {}


def test_load_data_key_invaild_because_of_children_rule():
    class Service1(Service):
        def getBindNames():
            return {
                "result": "result[...] name",
            }

        def getLoaders():
            def result():
                return {
                    "a": {
                        "c": "ccc",
                    },
                    "b": {
                        "c": "ccc",
                    },
                }

        def getRuleLists():
            return {
                "result": {
                    "properties": {
                        "result": {
                            "type": "object",
                        }
                    }
                },
                "result.a": {
                    "properties": {
                        "result": {
                            "properties": {
                                "a": {
                                    "type": "string",
                                }
                            }
                        }
                    }
                },
                "result.b": {
                    "properties": {
                        "result": {
                            "properties": {
                                "b": {
                                    "type": "object",
                                }
                            }
                        }
                    }
                },
            }

    service1 = Service1()
    service1.run()

    assert service1.getValidations()["result"] == False
