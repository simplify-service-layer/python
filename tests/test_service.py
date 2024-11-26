import json
import os
import sys

sys.path.append(os.getcwd())

from src.service import Service


def test_callback():
    class ParentService(Service):
        def getBindNames():
            return {"result": "name for result"}

        def getCallbacks():
            def result__cb1(result):
                result.update({"abcd": "aaaa"})

        def getLoaders():
            pass

        def getRuleLists():
            return {"result": {"required": ["result"]}}

    service = ParentService({"result": {"aaaa": "aaaa"}})
    service.run()

    assert service.getTotalErrors() == {}
    assert service.getData()["result"]["aaaa"] == "aaaa"
    assert service.getData()["result"]["abcd"] == "aaaa"


def test_callback_with_dependency():
    class ParentService1(Service):
        def getBindNames():
            return {"result": "name for result"}

        def getCallbacks():
            def result__cb1(result, test1):
                result.update({"abcd": test1})

            def result__cb2(result, test2):
                result.update({"bcde": test2})

        def getLoaders():
            def test1():
                return "test1 val"

        def getRuleLists():
            return {"result": {"required": ["result"]}}

    service1 = ParentService1({"result": {"aaaa": "aaaa"}})
    service1.run()

    assert service1.getTotalErrors() == {}
    assert service1.getData()["result"]["aaaa"] == "aaaa"
    assert service1.getData()["result"]["abcd"] == "test1 val"
    assert True == service1.getValidations()["result"]
    assert True == service1.getValidations()["test1"]
    assert True == service1.getValidations()["test2"]
    assert "bcde" not in dict(service1.getData()["result"]).keys()

    class ParentService2(Service):
        def getBindNames():
            return {
                "result": "name for result",
                "test2": "name for test2",
            }

        def getCallbacks():
            def result__cb1(result, test1):
                result.update({"abcd": test1})

            def result__cb2(result, test2):
                result.update({"bcde": test2})

        def getLoaders():
            def test1():
                return "test1 val"

        def getRuleLists():
            return {
                "result": {"required": ["result"]},
                "test2": {"required": ["test2"]},
            }

    service2 = ParentService2({"result": {"aaaa": "aaaa"}})
    service2.run()

    assert service2.getTotalErrors() != {}
    assert False == service2.getValidations()["result"]
    assert True == service2.getValidations()["test1"]
    assert False == service2.getValidations()["test2"]
    assert "abcd" not in dict(service2.getData()["result"]).keys()
    assert "bcde" not in dict(service2.getData()["result"]).keys()


def test_load_data_from_input():

    class ParentService(Service):
        def getBindNames():
            return {"result": "name for result"}

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


def test_load_data_from_loader_with_dependency():
    class Service1(Service):
        def getBindNames():
            return {
                "result": "name for result",
            }

        def getLoaders():
            def aaa():
                return "aaaaaa"

            def result(aaa):
                return aaa + " value"

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
    assert service1.getData()["result"] == "aaaaaa value"


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


def test_load_data_key_invaild_because_of_parent_rule():
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
                                    "type": "object",
                                    "required": ["d"],
                                }
                            }
                        }
                    }
                },
                "result.a.c": {
                    "properties": {
                        "result": {
                            "properties": {
                                "a": {
                                    "properties": {
                                        "c": {
                                            "type": "string",
                                        }
                                    },
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
                "result.b.c": {
                    "properties": {
                        "result": {
                            "properties": {
                                "b": {
                                    "properties": {
                                        "c": {
                                            "type": "string",
                                        }
                                    },
                                }
                            }
                        }
                    }
                },
            }

    service1 = Service1()
    service1.run()

    assert service1.getValidations()["result"] == False
    assert service1.getValidations()["result.a"] == False
    assert service1.getValidations()["result.a.c"] == False
    assert service1.getValidations()["result.b"] == True
    assert service1.getValidations()["result.b.c"] == True


def test_load_name():
    class Service1(Service):
        def getBindNames():
            return {}

        def getLoaders():
            pass

        def getRuleLists():
            return {
                "result": {
                    "required": ["result"],
                },
            }

    service = Service1({}, {"result": "result name"})
    service.run()

    assert service.getTotalErrors() != {}
    assert "result name" in service.getTotalErrors()["result"][0]


def test_load_name_bound():
    class Service1(Service):
        def getBindNames():
            return {"result": "result name"}

        def getLoaders():
            pass

        def getRuleLists():
            return {
                "result": {
                    "required": ["result"],
                },
            }

    service = Service1()
    service.run()

    assert service.getTotalErrors() != {}
    assert "result name" in service.getTotalErrors()["result"][0]


def test_load_name_bound_nested():
    class Service1(Service):
        def getBindNames():
            return {}

        def getLoaders():
            pass

        def getRuleLists():
            return {
                "result": {
                    "required": ["result"],
                },
            }

    service = Service1(
        {}, {"result": "{{abcd}}", "aaa": "aaaa", "abcd": "{{aaa}} bbb ccc ddd"}
    )
    service.run()

    assert service.getTotalErrors() != {}
    assert "aaaa bbb ccc ddd" in service.getTotalErrors()["result"][0]


def test_load_name_multidimension():
    class Service1(Service):
        def getBindNames():
            return {}

        def getLoaders():
            pass

        def getRuleLists():
            return {
                "result": {
                    "properties": {
                        "result": {
                            "properties": {
                                "a": {
                                    "required": ["b"],
                                }
                            },
                        },
                    },
                },
            }

    service = Service1(
        {"result": {"a": {}}},
        {"result": "result[...] name"},
    )
    service.run()

    assert service.getTotalErrors() != {}
    assert "result" in service.getTotalErrors()
    assert len(service.getTotalErrors()["result"]) == 1
    assert "result[a][b]" in service.getTotalErrors()["result"][0]
