import importlib.metadata
import logging
from typing import Any

logger = logging.getLogger("ripen.common.plugins")


class PluginLoader:
    """
    Handles dynamic discovery and loading of Ripen plugins using entry points.
    Plugins should be registered under the 'ripen.plugins' group.
    """

    GROUP_NAME = "ripen.plugins"

    @classmethod
    def load_all(cls, context: dict[str, Any]) -> list[Any]:
        """
        Scans for and initializes all registered plugins.
        Args:
            context: A shared context dictionary (e.g., config, UoW) to pass to plugins.
        Returns:
            A list of initialized plugin instances.
        """
        loaded_plugins = []

        try:
            # Discover entry points in the 'ripen.plugins' group
            eps = importlib.metadata.entry_points(group=cls.GROUP_NAME)

            if not eps:
                logger.debug("No Ripen plugins discovered.")
                return []

            for entry_point in eps:
                try:
                    logger.info(f"Loading plugin: {entry_point.name}...")

                    # Load the plugin class
                    plugin_class: type = entry_point.load()

                    # Instantiate the plugin
                    plugin_instance = plugin_class()

                    # Initialize the plugin with the shared context
                    if hasattr(plugin_instance, "initialize"):
                        plugin_instance.initialize(context)

                    loaded_plugins.append(plugin_instance)
                    logger.info(f"Plugin '{entry_point.name}' loaded and initialized.")

                except Exception as e:
                    logger.error(f"Failed to load plugin '{entry_point.name}': {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error during plugin discovery: {e}")

        return loaded_plugins
