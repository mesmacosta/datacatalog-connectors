#!/usr/bin/python
#
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from google.datacatalog_connectors.commons import utils

from google.api_core import exceptions
from google.cloud import datacatalog
from google.cloud.datacatalog import types


class DataCatalogFacade:
    """Wraps Data Catalog's API calls."""

    def __init__(self, project_id):
        self.__datacatalog = datacatalog.DataCatalogClient()
        self.__project_id = project_id

    def create_entry(self, entry_group_name, entry_id, entry):
        """Creates a Data Catalog Entry.

        :param entry_group_name: Parent Entry Group name.
        :param entry_id: Entry id.
        :param entry: An Entry object.
        :return: The created Entry.
        """
        try:
            entry = self.__datacatalog.create_entry(parent=entry_group_name,
                                                    entry_id=entry_id,
                                                    entry=entry)
            self.__log_entry_operation('created', entry=entry)
        except exceptions.PermissionDenied as e:
            entry_name = '{}/entries/{}'.format(entry_group_name, entry_id)
            self.__log_entry_operation('was not created',
                                       entry_name=entry_name)
            logging.warning('Error: %s', e)

        return entry

    def get_entry(self, name):
        """Retrieves Data Catalog Entry.

        :param name: The Entry name.
        :return: An Entry object if it exists.
        """
        return self.__datacatalog.get_entry(name=name)

    def update_entry(self, entry):
        """Updates an Entry.

        :param entry: An Entry object.
        :return: The updated Entry.
        """
        entry = self.__datacatalog.update_entry(entry=entry, update_mask=None)
        self.__log_entry_operation('updated', entry=entry)
        return entry

    def upsert_entry(self, entry_group_name, entry_id, entry):
        """
        Update a Data Catalog Entry if it exists and has been changed.
        Creates a new Entry if it does not exist.

        :param entry_group_name: Parent Entry Group name.
        :param entry_id: Entry id.
        :param entry: An Entry object.
        :return: The updated or created Entry.
        """
        persisted_entry = entry
        entry_name = '{}/entries/{}'.format(entry_group_name, entry_id)
        try:
            persisted_entry = self.get_entry(name=entry_name)
            self.__log_entry_operation('already exists', entry_name=entry_name)
            if self.__entry_was_updated(persisted_entry, entry):
                persisted_entry = self.update_entry(entry=entry)
            else:
                self.__log_entry_operation('is up-to-date',
                                           entry=persisted_entry)
        except exceptions.PermissionDenied:
            self.__log_entry_operation('does not exist', entry_name=entry_name)
            persisted_entry = self.create_entry(
                entry_group_name=entry_group_name,
                entry_id=entry_id,
                entry=entry)
        except exceptions.FailedPrecondition as e:
            logging.warning('Entry was not updated: %s', entry_name)
            logging.warning('Error: %s', e)

        return persisted_entry

    @classmethod
    def __entry_was_updated(cls, current_entry, new_entry):
        # Update time comparison allows to verify whether the entry was
        # updated on the source system.
        current_update_time = \
            current_entry.source_system_timestamps.update_time.seconds
        new_update_time = \
            new_entry.source_system_timestamps.update_time.seconds

        updated_time_changed = \
            new_update_time != 0 and current_update_time != new_update_time

        return updated_time_changed or not cls.__entries_are_equal(
            current_entry, new_entry)

    @classmethod
    def __entries_are_equal(cls, entry_1, entry_2):
        object_1 = utils.ValuesComparableObject()
        object_1.user_specified_system = entry_1.user_specified_system
        object_1.user_specified_type = entry_1.user_specified_type
        object_1.display_name = entry_1.display_name
        object_1.description = entry_1.description
        object_1.linked_resource = entry_1.linked_resource

        object_2 = utils.ValuesComparableObject()
        object_2.user_specified_system = entry_2.user_specified_system
        object_2.user_specified_type = entry_2.user_specified_type
        object_2.display_name = entry_2.display_name
        object_2.description = entry_2.description
        object_2.linked_resource = entry_2.linked_resource

        return object_1 == object_2

    def delete_entry(self, name):
        """Deletes a Data Catalog Entry.

        :param name: The Entry name.
        """
        try:
            self.__datacatalog.delete_entry(name=name)
            self.__log_entry_operation('deleted', entry_name=name)
        except Exception as e:
            logging.info(
                'An exception ocurred while attempting to'
                ' delete Entry: %s', name)
            logging.debug(str(e))

    @classmethod
    def __log_entry_operation(cls, description, entry=None, entry_name=None):

        formatted_description = 'Entry {}: '.format(description)
        logging.info('%s%s', formatted_description,
                     entry.name if entry else entry_name)

        if entry:
            logging.info('%s^ [%s] %s', ' ' * len(formatted_description),
                         entry.user_specified_type, entry.linked_resource)

    def create_entry_group(self, location_id, entry_group_id):
        """Creates a Data Catalog Entry Group.

        :param location_id: Location id.
        :param entry_group_id: Entry Group id.
        :return: The created Entry Group.
        """
        entry_group = self.__datacatalog.create_entry_group(
            parent=datacatalog.DataCatalogClient.location_path(
                self.__project_id, location_id),
            entry_group_id=entry_group_id,
            entry_group={})
        logging.info('Entry Group created: %s', entry_group.name)
        return entry_group

    def delete_entry_group(self, name):
        """
        Deletes a Data Catalog Entry Group.

        :param name: The Entry Group name.
        """
        self.__datacatalog.delete_entry_group(name=name)

    def create_tag_template(self, location_id, tag_template_id, tag_template):
        """Creates a Data Catalog Tag Template.

        :param location_id: Location id.
        :param tag_template_id: Tag Template id.
        :param tag_template: A Tag Template object.
        :return: The created Tag Template.
        """
        return self.__datacatalog.create_tag_template(
            parent=datacatalog.DataCatalogClient.location_path(
                self.__project_id, location_id),
            tag_template_id=tag_template_id,
            tag_template=tag_template)

    def get_tag_template(self, name):
        """Retrieves a Data Catalog Tag Template.

        :param name: The Tag Templane name.
        :return: A Tag Template object if it exists.
        """
        return self.__datacatalog.get_tag_template(name=name)

    def delete_tag_template(self, name):
        """Deletes a Data Catalog Tag Template.

        :param name: The Tag Template name.
        """
        self.__datacatalog.delete_tag_template(name=name, force=True)
        logging.info('Tag Template deleted: %s', name)

    def create_tag(self, entry_name, tag):
        """Creates a Data Catalog Tag.

        :param entry_name: Parent Entry name.
        :param tag: A Tag object.
        :return: The created Tag.
        """
        return self.__datacatalog.create_tag(parent=entry_name, tag=tag)

    def list_tags(self, entry_name):
        """List Tags for a given Entry.

        :param entry_name: The parent Entry name.
        :return: A list of Tag objects.
        """
        return self.__datacatalog.list_tags(parent=entry_name)

    def update_tag(self, tag):
        """Updates a Tag.

        :param tag: A Tag object.
        :return: The updated Tag.
        """
        return self.__datacatalog.update_tag(tag=tag, update_mask=None)

    def upsert_tags(self, entry, tags):
        """Updates or creates Tag for a given Entry.

        :param entry: The Entry object.
        :param tags: A list of Tag objects.
        """
        if not tags:
            return

        persisted_tags = self.list_tags(entry.name)

        for tag in tags:
            logging.info('Processing Tag from Template: %s ...', tag.template)

            tag_to_create = tag
            tag_to_update = None
            for persisted_tag in persisted_tags:
                if tag.template == persisted_tag.template:
                    tag_to_create = None
                    tag.name = persisted_tag.name
                    if not self.__tags_fields_are_equal(tag, persisted_tag):
                        tag_to_update = tag

            if tag_to_create:
                created_tag = self.create_tag(entry.name, tag_to_create)
                logging.info('Tag created: %s', created_tag.name)
            elif tag_to_update:
                self.update_tag(tag_to_update)
                logging.info('Tag updated: %s', tag_to_update.name)
            else:
                logging.info('Tag is up-to-date: %s', tag.name)

    @classmethod
    def __tags_fields_are_equal(cls, tag_1, tag_2):
        for field_id in tag_1.fields:
            tag_1_field = tag_1.fields[field_id]
            tag_2_field = tag_2.fields[field_id]

            values_are_equal = tag_1_field.bool_value == \
                tag_2_field.bool_value
            values_are_equal = values_are_equal \
                and tag_1_field.double_value == tag_2_field.double_value
            values_are_equal = values_are_equal \
                and tag_1_field.string_value == tag_2_field.string_value
            values_are_equal = values_are_equal \
                and tag_1_field.timestamp_value.seconds == \
                tag_2_field.timestamp_value.seconds
            values_are_equal = values_are_equal \
                and tag_1_field.enum_value.display_name == \
                tag_2_field.enum_value.display_name

            if not values_are_equal:
                return False

        return True

    def search_catalog(self, query):
        """Searches Data Catalog for a given query.

        :param query: The query string.
        :return: A Search Result list.
        """
        scope = types.SearchCatalogRequest.Scope()
        scope.include_project_ids.append(self.__project_id)

        return [
            result for result in self.__datacatalog.search_catalog(
                scope=scope, query=query, order_by='relevance', page_size=1000)
        ]

    def search_catalog_relative_resource_name(self, query):
        """Searches Data Catalog for a given query.

        :param query: The query string.
        :return: A string list in which each element represents
        an Entry resource name.
        """
        return [
            result.relative_resource_name
            for result in self.search_catalog(query=query)
        ]
