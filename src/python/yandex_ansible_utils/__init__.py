"""Dependency carrier for the ``ysignat.yandex`` Ansible collection.

The collection is installed by ``ansible-galaxy``, which does not install its
controller-side Python dependencies.  This intentionally minimal companion
package lets Poetry-based controller projects depend on the collection's
requirements through a normal dependency management.
"""
