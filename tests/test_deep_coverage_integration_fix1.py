from iip.coverage.portfolio_integration import IntegrationNode, plan


def test_enabled_duplicate_wins():
    result = plan(
        (
            IntegrationNode("portfolio"),
            IntegrationNode("atlas"),
            IntegrationNode("portfolio", False),
        )
    )
    assert result.ready
    assert tuple(node.name for node in result.nodes) == ("atlas", "portfolio")
    assert all(node.enabled for node in result.nodes)


def test_disabled_only_node_remains_disabled():
    result = plan(
        (
            IntegrationNode("portfolio", False),
            IntegrationNode("atlas"),
        )
    )
    assert not result.ready
    assert result.nodes[1].name == "portfolio" or result.nodes[0].name == "portfolio"


def test_duplicate_enabled_nodes_are_deterministic():
    result = plan(
        (
            IntegrationNode("portfolio", True),
            IntegrationNode("portfolio", True),
        )
    )
    assert result.ready
    assert len(result.nodes) == 1
