from app.database.models.complaint import Complaint
from app.repositories.base_repository import BaseRepository


class ComplaintRepository(BaseRepository):

    def create(self, complaint):

        self.db.add(complaint)

        self.db.commit()

        self.db.refresh(complaint)

        return complaint