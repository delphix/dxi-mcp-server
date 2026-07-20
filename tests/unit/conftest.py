"""
Unit test conftest.

pytest_configure runs before pytest_load_initial_conftests of plugins (trylast),
so putting the pydantic warmup here in a pytest_configure hook (tryfirst) ensures
it runs before coverage's InOrOut.__init__ imports our source modules.
"""


def pytest_configure(config):
    """Warm up pydantic before pytest-cov's coverage.start() runs.

    pytest-cov's pytest_load_initial_conftests (tryfirst) calls coverage.start()
    which internally does sys_modules_saved() + import of the source module. This
    triggers mcp.types.JSONRPCMessage(RootModel[...]) BEFORE pydantic.root_model
    is in sys.modules, causing KeyError: 'pydantic.root_model'.

    Importing RootModel here (tryfirst pytest_configure) puts pydantic.root_model
    into sys.modules BEFORE coverage starts.
    """
    from pydantic import RootModel  # noqa: F401
