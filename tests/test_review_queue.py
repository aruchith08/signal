"""
Unit Tests for ReviewQueueService
"""
import unittest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from apps.api.models import Base, Opportunity
from services.verification.review_queue import ReviewQueueService
from shared.constants import ReviewStatus, ReviewPriority


class TestReviewQueueService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

        async with self.session_factory() as session:
            opp = Opportunity(title="Ambiguous Contest", slug="ambiguous-contest-123")
            session.add(opp)
            await session.commit()
            self.opp_id = opp.id

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def test_enqueue_approve_and_reject(self):
        async with self.session_factory() as session:
            service = ReviewQueueService(session)
            review = await service.enqueue_review(
                entity_id=self.opp_id,
                reason="Ambiguous season match",
                priority=ReviewPriority.HIGH,
            )
            self.assertEqual(review.status, ReviewStatus.OPEN.value)
            self.assertEqual(review.priority, ReviewPriority.HIGH.value)

            queue = await service.get_queue(status=ReviewStatus.OPEN.value)
            self.assertTrue(any(r.id == review.id for r in queue))

            # Approve
            approved = await service.approve_review(review.id, notes="Manually confirmed")
            self.assertEqual(approved.status, ReviewStatus.APPROVED.value)
            self.assertIsNotNone(approved.resolved_at)


if __name__ == "__main__":
    unittest.main()
