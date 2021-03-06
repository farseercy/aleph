from aleph.core import db
from aleph.model.common import SoftDeleteModel, IdModel


class Permission(db.Model, IdModel, SoftDeleteModel):
    """A set of rights granted to a role on a resource."""
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), index=True)
    read = db.Column(db.Boolean, default=False)
    write = db.Column(db.Boolean, default=False)
    collection_id = db.Column(db.Integer, nullable=False)

    @classmethod
    def grant(cls, collection, role, read, write):
        permission = cls.by_collection_role(collection, role)
        if permission is None:
            permission = Permission()
            permission.role_id = role.id
            permission.collection_id = collection.id
        permission.read = read
        permission.write = write
        db.session.add(permission)
        db.session.flush()
        return permission

    @classmethod
    def by_collection_role(cls, collection, role):
        q = cls.all()
        q = q.filter(Permission.role_id == role.id)
        q = q.filter(Permission.collection_id == collection.id)
        permission = q.first()
        return permission
