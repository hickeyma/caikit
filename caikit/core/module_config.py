# Standard
import os

# First Party
import aconfig
import alog

# Local
from . import toolkit
from .toolkit import error_handler

log = alog.use_channel("MODULE")
error = error_handler.get(log)


class ModuleConfig(aconfig.Config):
    """Config object used by all blocks for config loading, saving, etc."""

    # keys that are not allowed at the top-level module configuration (reserved for internal use)
    reserved_keys = "module_id", "model_path"

    def __init__(self, config_dict):
        """Construct a new module configuration object from a dictionary of config options.

        Args:
            config_dict:  dict
                Dictionary or containing the module's configuration.

        Notes:
            The following keys are reserved and *must not* be specified at the top level of a
            configuration:

            module_id - reserved for storing the block or workflow id
            model_path - reserved for storing the original location where the model was loaded from
        """
        super().__init__(config_dict, override_env_vars=False)

        # validate that reserved configuration items are not in the config_dict
        self_keys_lower = {key.lower() for key in self.keys()}
        for reserved_key in self.reserved_keys:
            if reserved_key.lower() in self_keys_lower:
                error(
                    "<COR80419305E>",
                    KeyError(
                        "Do not add `{}` as top-level key in `config.yml`. "
                        "This is for internal use only.".format(reserved_key)
                    ),
                )

        # Alias from the subtype id to module_id
        self.module_id = None
        # 🌶️🌶️🌶️: Delayed import here to avoid circular dependency
        # Needs a bit more ♻️ to be less 💩
        # pylint: disable=import-outside-toplevel,no-name-in-module
        # Local
        from caikit.core import _MODULE_TYPES

        for subtype in _MODULE_TYPES:
            id_field = f"{subtype.lower()}_id"
            subtype_id_val = getattr(self, id_field, None)
            if subtype_id_val is not None:
                error.type_check(
                    "<COR80419079E>",
                    str,
                    **{id_field: subtype_id_val},
                )
                self.module_id = subtype_id_val
                break
        error.value_check(
            "<COR80418932E>",
            self.module_id is not None,
            "Please specify one of {} in model config.",
            [f"{subtype.lower()}_id" for subtype in _MODULE_TYPES],
        )

    @classmethod
    def load(cls, model_path):
        """Load a new module configuration from a directory on disk.

        Args:
            model_path: str
                Path to model directory. At the top level of directory is `config.yml` which holds
                info about the model. Note that the model_path here is assumed to be operating
                system correct as a consequence of the way this method is invoked by the model
                manager.

        Returns:
            BlockConfig
                Instantiated BlockConfig for model given model_path.
        """
        error.type_check("<COR71170339E>", str, model_path=model_path)

        # validate config.yml
        config_path = os.path.join(model_path, "config.yml")
        if not (os.path.exists(config_path) and os.path.isfile(config_path)):
            # NOTE: Do not log this out with error handler, as we might try this function multiple
            # times in some special cases, e.g., when handling zip archives.
            raise FileNotFoundError(
                "Module path `{}` is not a directory with a `config.yml` file.".format(
                    model_path
                )
            )

        # read the yaml to dict and construct a new config object
        config = cls(toolkit.load_yaml(config_path))

        # error if add model_path was in the config
        if config.model_path is not None:
            error(
                "<COR80166142E>",
                KeyError(
                    "Do not add `model_path` as top-level key in `config.yml`. "
                    "This is for internal use only."
                ),
            )

        # add the model path to the config object
        config["model_path"] = model_path

        return config

    def save(self, model_path):
        """Save this module configuration to a top-level `config.yml` file in the specified
        model path.

        Args:  str
            Path to model directory.  The `config.yml` file will be written to this location.

        Notes:
            `model_path` must already exist!  This means you must create the directory outside of
            this routine.
        """
        # make operating-system correct
        model_path = os.path.normpath(model_path)

        # create the directory where this config will be saved
        os.makedirs(model_path, exist_ok=True)

        # full path to config.yml
        config_path = os.path.join(model_path, "config.yml")

        # cast self into a dict and make sure we have a copy
        config_dict = dict(self).copy()

        # remove any reserved keys, these will be reproduced at load time
        for reserved_key in self.reserved_keys:
            if reserved_key in config_dict:
                config_dict.pop(reserved_key)

        # write to file
        toolkit.save_yaml(config_dict, config_path)
