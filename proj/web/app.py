from typing import Type

import waitress
from flask import Flask
from flask_restful import Api

from proj.config_parser import Config
from proj.database.database_manager import DatabaseManager
from proj.web.base_resource import BaseResource
from proj.web.resources.debug.config import DebugConfigResource
from proj.web.resources.debug.database import DebugDatabaseResource
from proj.web.resources.index import IndexResource


class WebApp:
    def __init__(self, config: Config):
        self.config = config

        # Database setup
        self.db = DatabaseManager(config)
        self.db.create_tables()
        self.db.migrate()

        # Flask setup
        self.app = Flask(__name__)
        self.db.attach_flask(self.app)

        # Flask-RESTful setup
        self.api = Api()
        self.register_resources()
        self.api.init_app(self.app)

    def register_resources(self):
        """
        Registers the API resources.
        """
        # todo: auto-discovery?

        self.register_resource(IndexResource)
        if self.config.get("debug") is True:
            # debug routes
            self.register_resource(DebugDatabaseResource)
            self.register_resource(DebugConfigResource)

    def register_resource(self, resource_class: Type[BaseResource]):
        """
        Registers a resource to the Flask-RESTful API instance
        :param resource_class: the class of the resource
        """
        class_setup = resource_class.setup(self)
        endpoint = resource_class.name
        self.api.add_resource(
            class_setup,
            resource_class.url,
            endpoint=endpoint
        )

    def serve(self):
        waitress.serve(self.app,
                       host=self.config.get("web", "ip"),
                       port=self.config.get("web", "port"))