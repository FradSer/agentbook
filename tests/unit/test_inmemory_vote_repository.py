from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.errors import DuplicateVoteError
from app.domain.models import Vote
from app.infrastructure.persistence.in_memory import InMemoryVoteRepository


def test_inmemory_vote_repository_rejects_duplicate_vote_pair() -> None:
    repository = InMemoryVoteRepository()
    comment_id = uuid4()
    voter_id = uuid4()

    repository.add(Vote(comment_id=comment_id, voter_id=voter_id, vote_type="upvote"))

    with pytest.raises(DuplicateVoteError):
        repository.add(
            Vote(comment_id=comment_id, voter_id=voter_id, vote_type="upvote")
        )
