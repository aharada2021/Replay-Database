"""
Comment count functionality tests.

Tests for:
- BattleTableClient.update_comment_count (unit)
- update_battle_comment_count (integration across game type tables)
- handle_post_comment / handle_delete_comment (comment count side effects)
"""

import json
import time
import unittest
from unittest.mock import MagicMock, patch, call

from botocore.exceptions import ClientError


class TestBattleTableClientUpdateCommentCount(unittest.TestCase):
    """Unit tests for BattleTableClient.update_comment_count"""

    def _make_client(self, game_type="clan"):
        """Create a BattleTableClient with a mocked DynamoDB table."""
        with patch("utils.dynamodb_tables.boto3"):
            from utils.dynamodb_tables import BattleTableClient

            client = BattleTableClient(game_type)
            client.table = MagicMock()
            return client

    def test_returns_true_when_update_succeeds(self):
        """update_comment_count returns True when DynamoDB update succeeds."""
        client = self._make_client()
        client.table.update_item.return_value = {}

        result = client.update_comment_count("arena-123", delta=1)

        self.assertTrue(result)
        client.table.update_item.assert_called_once_with(
            Key={"arenaUniqueID": "arena-123", "recordType": "MATCH"},
            UpdateExpression="SET commentCount = if_not_exists(commentCount, :zero) + :delta",
            ExpressionAttributeValues={":zero": 0, ":delta": 1},
            ConditionExpression="attribute_exists(arenaUniqueID)",
        )

    def test_returns_false_on_conditional_check_failed(self):
        """update_comment_count returns False when MATCH record does not exist."""
        client = self._make_client()
        error_response = {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "Condition not met",
            }
        }
        client.table.update_item.side_effect = ClientError(
            error_response, "UpdateItem"
        )

        result = client.update_comment_count("arena-missing", delta=1)

        self.assertFalse(result)

    def test_reraises_on_other_dynamodb_errors(self):
        """update_comment_count re-raises non-ConditionalCheckFailed errors."""
        client = self._make_client()
        error_response = {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Rate exceeded",
            }
        }
        client.table.update_item.side_effect = ClientError(
            error_response, "UpdateItem"
        )

        with self.assertRaises(ClientError) as ctx:
            client.update_comment_count("arena-123", delta=1)

        self.assertEqual(
            ctx.exception.response["Error"]["Code"],
            "ProvisionedThroughputExceededException",
        )

    def test_passes_negative_delta_for_decrement(self):
        """update_comment_count correctly passes negative delta."""
        client = self._make_client()
        client.table.update_item.return_value = {}

        result = client.update_comment_count("arena-123", delta=-1)

        self.assertTrue(result)
        call_kwargs = client.table.update_item.call_args[1]
        self.assertEqual(call_kwargs["ExpressionAttributeValues"][":delta"], -1)


class TestUpdateBattleCommentCount(unittest.TestCase):
    """Integration tests for update_battle_comment_count across game type tables."""

    @patch("handlers.api.comments.BattleTableClient")
    def test_stops_at_first_matching_table(self, mock_client_cls):
        """Stops iterating when the first table returns True (clan table)."""
        from handlers.api.comments import update_battle_comment_count

        mock_instance = MagicMock()
        mock_instance.update_comment_count.return_value = True
        mock_client_cls.return_value = mock_instance

        update_battle_comment_count("arena-123", delta=1)

        # Should only be called once since clan table matched
        mock_client_cls.assert_called_once_with("clan")
        mock_instance.update_comment_count.assert_called_once_with("arena-123", 1)

    @patch("handlers.api.comments.BattleTableClient")
    def test_tries_ranked_when_clan_returns_false(self, mock_client_cls):
        """Tries ranked table when clan table returns False."""
        from handlers.api.comments import update_battle_comment_count

        instances = []

        def create_instance(game_type):
            mock = MagicMock()
            mock.game_type = game_type
            if game_type == "ranked":
                mock.update_comment_count.return_value = True
            else:
                mock.update_comment_count.return_value = False
            instances.append(mock)
            return mock

        mock_client_cls.side_effect = create_instance

        update_battle_comment_count("arena-456", delta=1)

        # Should have tried clan (False) then ranked (True)
        self.assertEqual(len(instances), 2)
        self.assertEqual(mock_client_cls.call_args_list, [call("clan"), call("ranked")])
        instances[0].update_comment_count.assert_called_once_with("arena-456", 1)
        instances[1].update_comment_count.assert_called_once_with("arena-456", 1)

    @patch("handlers.api.comments.BattleTableClient")
    def test_tries_all_tables_when_none_match(self, mock_client_cls):
        """Tries all four tables when match is not found in any."""
        from handlers.api.comments import update_battle_comment_count

        mock_instance = MagicMock()
        mock_instance.update_comment_count.return_value = False
        mock_client_cls.return_value = mock_instance

        update_battle_comment_count("arena-unknown", delta=1)

        expected_calls = [call("clan"), call("ranked"), call("random"), call("other")]
        self.assertEqual(mock_client_cls.call_args_list, expected_calls)
        self.assertEqual(mock_instance.update_comment_count.call_count, 4)

    @patch("handlers.api.comments.BattleTableClient")
    def test_catches_exception_and_logs(self, mock_client_cls):
        """Catches exceptions from BattleTableClient and logs error."""
        from handlers.api.comments import update_battle_comment_count

        mock_instance = MagicMock()
        mock_instance.update_comment_count.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "boom"}},
            "UpdateItem",
        )
        mock_client_cls.return_value = mock_instance

        # Should not raise -- the function catches and logs
        update_battle_comment_count("arena-err", delta=1)


class TestHandlePostCommentCountIncrement(unittest.TestCase):
    """Tests that handle_post_comment increments the comment count."""

    def _build_event(self, arena_unique_id, session_id="valid-session"):
        return {
            "requestContext": {"http": {"method": "POST"}},
            "rawPath": f"/api/comments/{arena_unique_id}",
            "pathParameters": {"arenaUniqueID": arena_unique_id},
            "headers": {"origin": "http://localhost:3000", "cookie": f"session_id={session_id}"},
            "cookies": [f"session_id={session_id}"],
            "body": json.dumps({"content": "Nice game!"}),
        }

    @patch("handlers.api.comments.update_battle_comment_count")
    @patch("handlers.api.comments.comments_table")
    @patch("handlers.api.comments.sessions_table")
    def test_increments_count_on_post(self, mock_sessions, mock_comments, mock_update):
        """handle_post_comment calls update_battle_comment_count with delta=1."""
        from handlers.api.comments import handle_post_comment

        mock_sessions.get_item.return_value = {
            "Item": {
                "sessionId": "valid-session",
                "discordUserId": "user-1",
                "discordUsername": "TestUser",
                "discordGlobalName": "Test User",
                "discordAvatar": "abc",
                "expiresAt": int(time.time()) + 3600,
            }
        }
        mock_comments.put_item.return_value = {}

        event = self._build_event("arena-post-test")
        cors_headers = {"Access-Control-Allow-Origin": "*"}

        response = handle_post_comment(event, "arena-post-test", cors_headers)

        self.assertEqual(response["statusCode"], 201)
        mock_update.assert_called_once_with("arena-post-test", delta=1)


class TestHandleDeleteCommentCountDecrement(unittest.TestCase):
    """Tests that handle_delete_comment decrements the comment count."""

    def _build_event(self, arena_unique_id, comment_id, session_id="valid-session"):
        return {
            "requestContext": {"http": {"method": "DELETE"}},
            "rawPath": f"/api/comments/{arena_unique_id}/{comment_id}",
            "pathParameters": {
                "arenaUniqueID": arena_unique_id,
                "commentId": comment_id,
            },
            "headers": {"origin": "http://localhost:3000", "cookie": f"session_id={session_id}"},
            "cookies": [f"session_id={session_id}"],
            "body": "",
        }

    @patch("handlers.api.comments.update_battle_comment_count")
    @patch("handlers.api.comments.comments_table")
    @patch("handlers.api.comments.sessions_table")
    def test_decrements_count_on_delete(self, mock_sessions, mock_comments, mock_update):
        """handle_delete_comment calls update_battle_comment_count with delta=-1."""
        from handlers.api.comments import handle_delete_comment

        mock_sessions.get_item.return_value = {
            "Item": {
                "sessionId": "valid-session",
                "discordUserId": "user-1",
                "discordUsername": "TestUser",
                "discordGlobalName": "Test User",
                "discordAvatar": "abc",
                "expiresAt": int(time.time()) + 3600,
            }
        }
        mock_comments.delete_item.return_value = {}

        event = self._build_event("arena-del-test", "comment-1")
        cors_headers = {"Access-Control-Allow-Origin": "*"}

        response = handle_delete_comment(event, "arena-del-test", "comment-1", cors_headers)

        self.assertEqual(response["statusCode"], 200)
        mock_update.assert_called_once_with("arena-del-test", delta=-1)


if __name__ == "__main__":
    unittest.main()
