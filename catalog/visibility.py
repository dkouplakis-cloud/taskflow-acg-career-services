
"""
Centralized catalogue visibility rules for TaskFlow.

A category is publicly visible only when it and
all of its ancestors are active.
"""

from collections import defaultdict

from .models import Category


def get_visible_category_ids():
    """
    Return the IDs of categories that belong to
    a completely active category hierarchy.

    Fetch active categories in a single database
    query and traverse from active root categories.
    """

    active_categories = Category.objects.filter(
        is_active=True
    ).values_list("pk", "parent_id")

    children_by_parent = defaultdict(list)

    # Organize active categories by their parent IDs.
    for category_id, parent_id in active_categories:
        children_by_parent[parent_id].append(
            category_id
        )

    visible_ids = set()

    # Start with active top-level categories.
    pending = list(children_by_parent[None])

    while pending:
        category_id = pending.pop()

        # Prevent repeated traversal of a category.
        if category_id in visible_ids:
            continue

        visible_ids.add(category_id)

        # Visit children only after confirming that
        # their parent belongs to a visible hierarchy.
        pending.extend(
            children_by_parent[category_id]
        )

    return visible_ids

def get_visible_subtree_ids(visible_categories, selected_slug):
    """
    Return the selected visible category and all
    of its publicly visible descendants.

    Unknown or hidden category slugs return an
    empty set to prevent unintended results.
    """

    children_by_parent = defaultdict(list)
    selected_id = None

    # Build the hierarchy using visible categories only.
    for category in visible_categories:
        children_by_parent[category.parent_id].append(
            category.pk
        )

        if category.slug == selected_slug:
            selected_id = category.pk

    # Reject categories outside the visible hierarchy.
    if selected_id is None:
        return set()

    subtree_ids = set()
    pending = [selected_id]

    # Traverse the selected category and its descendants.
    while pending:
        category_id = pending.pop()

        if category_id in subtree_ids:
            continue

        subtree_ids.add(category_id)

        pending.extend(
            children_by_parent[category_id]
        )

    return subtree_ids