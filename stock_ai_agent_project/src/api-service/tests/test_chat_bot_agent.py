"""
Unit tests for the ChatAgent and related models.
"""

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.unit


class TestUserPreferenceModel:
    """Tests for the user_preference Pydantic model."""

    def test_valid_user_preference_creation(self):
        """Test creating a valid user preference."""
        from api.utils.chat_bot_agent import user_preference

        pref = user_preference(
            long_term=True,
            short_term=False,
            high_risk=False,
            low_risk=True,
            completed=True,
            confirmation=True,
        )
        assert pref.long_term is True
        assert pref.short_term is False
        assert pref.completed is True

    def test_user_preference_all_false(self):
        """Test user preference with all false values."""
        from api.utils.chat_bot_agent import user_preference

        pref = user_preference(
            long_term=False,
            short_term=False,
            high_risk=False,
            low_risk=False,
            completed=False,
            confirmation=False,
        )
        assert pref.long_term is False
        assert pref.confirmation is False

    def test_user_preference_all_true(self):
        """Test user preference with all true values."""
        from api.utils.chat_bot_agent import user_preference

        pref = user_preference(
            long_term=True,
            short_term=True,
            high_risk=True,
            low_risk=True,
            completed=True,
            confirmation=True,
        )
        assert pref.long_term is True
        assert pref.high_risk is True

    def test_user_preference_model_dump(self):
        """Test converting user preference to dictionary."""
        from api.utils.chat_bot_agent import user_preference

        pref = user_preference(
            long_term=True,
            short_term=False,
            high_risk=True,
            low_risk=False,
            completed=True,
            confirmation=False,
        )
        result = pref.model_dump()
        assert isinstance(result, dict)
        assert result["long_term"] is True
        assert result["confirmation"] is False
        assert len(result) == 6

    def test_user_preference_field_descriptions(self):
        """Test that field descriptions are set correctly."""
        from api.utils.chat_bot_agent import user_preference

        schema = user_preference.model_json_schema()
        properties = schema.get("properties", {})
        assert "long_term" in properties
        assert "description" in properties["long_term"]


class TestChatAgentState:
    """Tests for ChatAgentState type."""

    def test_chat_agent_state_has_messages(self):
        """Test ChatAgentState has messages field."""
        from api.utils.chat_bot_agent import ChatAgentState

        annotations = ChatAgentState.__annotations__
        assert "messages" in annotations

    def test_chat_agent_state_has_user_pref(self):
        """Test ChatAgentState has user_pref field."""
        from api.utils.chat_bot_agent import ChatAgentState

        annotations = ChatAgentState.__annotations__
        assert "user_pref" in annotations


class TestChatAgent:
    """Tests for ChatAgent class."""

    @pytest.fixture
    def mock_model(self):
        """Create a mock LLM model."""
        mock = MagicMock()
        mock.invoke.return_value = MagicMock(content="Test response")
        mock.with_structured_output.return_value.invoke.return_value = MagicMock(
            model_dump=lambda: {
                "long_term": True,
                "short_term": False,
                "high_risk": False,
                "low_risk": True,
                "completed": False,
                "confirmation": False,
            }
        )
        return mock

    @pytest.fixture
    def mock_checkpointer(self):
        """Create a mock checkpointer."""
        return MagicMock()

    def test_chat_agent_initialization(self, mock_model, mock_checkpointer):
        """Test ChatAgent initializes correctly."""
        from api.utils.chat_bot_agent import ChatAgent

        agent = ChatAgent(
            model=mock_model,
            tools=[],
            checkpointer=mock_checkpointer,
            system="Test system prompt",
        )

        assert agent.system == "Test system prompt"
        assert agent.model == mock_model
        assert agent.graph is not None

    def test_chat_agent_empty_system_prompt(self, mock_model, mock_checkpointer):
        """Test ChatAgent with empty system prompt."""
        from api.utils.chat_bot_agent import ChatAgent

        agent = ChatAgent(model=mock_model, tools=[], checkpointer=mock_checkpointer, system="")

        assert agent.system == ""

    def test_chat_agent_stores_tools(self, mock_model, mock_checkpointer):
        """Test ChatAgent stores tools correctly."""
        from api.utils.chat_bot_agent import ChatAgent

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"

        agent = ChatAgent(
            model=mock_model,
            tools=[mock_tool],
            checkpointer=mock_checkpointer,
            system="Test",
        )

        assert "test_tool" in agent.tools

    def test_chat_agent_multiple_tools(self, mock_model, mock_checkpointer):
        """Test ChatAgent with multiple tools."""
        from api.utils.chat_bot_agent import ChatAgent

        tool1 = MagicMock(name="tool1")
        tool1.name = "tool1"
        tool2 = MagicMock(name="tool2")
        tool2.name = "tool2"

        agent = ChatAgent(
            model=mock_model,
            tools=[tool1, tool2],
            checkpointer=mock_checkpointer,
            system="Test",
        )

        assert len(agent.tools) == 2

    def test_call_llm_invokes_model(self, mock_model, mock_checkpointer):
        """Test call_llm invokes the model."""
        from api.utils.chat_bot_agent import ChatAgent

        agent = ChatAgent(
            model=mock_model,
            tools=[],
            checkpointer=mock_checkpointer,
            system="You are a helpful assistant.",
        )

        state = {"messages": [MagicMock()], "user_pref": {}}
        result = agent.call_llm(state)

        assert "messages" in result
        mock_model.invoke.assert_called_once()

    def test_validate_llm_not_completed(self, mock_model, mock_checkpointer):
        """Test validate_llm returns empty user_pref when not completed."""
        from api.utils.chat_bot_agent import ChatAgent

        agent = ChatAgent(model=mock_model, tools=[], checkpointer=mock_checkpointer, system="Test")

        state = {"messages": [MagicMock(content="Test message")], "user_pref": {}}
        result = agent.validate_llm(state)

        assert result["user_pref"] == {}

    def test_validate_llm_completed(self, mock_model, mock_checkpointer):
        """Test validate_llm returns user_pref when completed."""
        from api.utils.chat_bot_agent import ChatAgent

        mock_model.with_structured_output.return_value.invoke.return_value = MagicMock(
            model_dump=lambda: {
                "long_term": True,
                "short_term": False,
                "high_risk": False,
                "low_risk": True,
                "completed": True,
                "confirmation": True,
            }
        )

        agent = ChatAgent(model=mock_model, tools=[], checkpointer=mock_checkpointer, system="Test")

        state = {"messages": [MagicMock(content="Test message")], "user_pref": {}}
        result = agent.validate_llm(state)

        assert result["user_pref"]["completed"] is True
        assert result["user_pref"]["long_term"] is True
