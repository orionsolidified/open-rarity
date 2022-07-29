import requests
from openrarity.models.token_metadata import (
    StringAttributeValue,
    TokenMetadata,
)
from openrarity.models.collection import Collection
from openrarity.models.collection_identifier import OpenseaCollectionIdentifier
from openrarity.resolver.models.collection_with_metadata import CollectionWithMetadata
from openrarity.models.chain import Chain
import logging

logger = logging.getLogger("opensea_api_helpers")

# https://docs.opensea.io/reference/retrieving-a-single-collection
OS_COLLECTION_URL = "https://api.opensea.io/api/v1/collection/{slug}"
OS_ASSETS_URL = "https://api.opensea.io/api/v1/assets"

HEADERS = {
    "Accept": "application/json",
    "X-API-KEY": "",
}

def fetch_opensea_collection_data(slug: str):
    response = requests.get(OS_COLLECTION_URL.format(slug=slug))

    if response.status_code != 200:
        logger.debug(
            f"[Opensea] Failed to resolve collection {slug}."
            f"Received {response.status_code}: {response.reason}. {response.json()}"
        )

        raise Exception(f"[Opensea] Failed to resolve collection with slug {slug}")

    return response.json()["collection"]


def fetch_opensea_assets_data(slug: str, token_ids: list[int], limit=30):
    assert len(token_ids) < limit
    querystring = {
        "token_ids": token_ids,
        "collection_slug": slug,
        "order_direction": "desc",
        "offset": "0",
        "limit": limit,
    }

    response = requests.request(
        "GET",
        OS_ASSETS_URL,
        headers=HEADERS,
        params=querystring,
    )

    if response.status_code != 200:
        logger.debug(
            f"[Opensea] Failed to resolve assets for {slug}."
            f"Received {response.status_code}: {response.reason}. {response.json()}"
        )
        raise Exception(f"[Opensea] Failed to resolve assets with slug {slug}")

    return response.json()["assets"]


def opensea_traits_to_token_metadata(asset_traits: dict) -> TokenMetadata:
    """
    Args:
        asset_traits (dict): the "traits" field for an asset in the return value
        of Opensea's asset(s) endpoint
    """
    # TODO[impreso] filter out numeric traits
    return TokenMetadata(
        string_attributes={
            trait["trait_type"]: StringAttributeValue(
                attribute_name=trait["trait_type"],
                attribute_value=trait["value"],
                count=trait["trait_count"],
            )
            for trait in asset_traits
        }
    )


def get_collection_with_metadata(collection_slug: str) -> CollectionWithMetadata:
    """Fetches collection metadata with OpenSea endpoint and API key
    and stores it in the Collection object

    Parameters
    ----------
    collection_slug : str
        collection slug on opensea's system
    tokens : list[Token]
        list of tokens to resolve metadata for

    Returns
    -------
    Collection
        collection abstraction

    """
    collection_obj = fetch_opensea_collection_data(slug=collection_slug)
    contracts = collection_obj["primary_asset_contracts"]
    interfaces = set([contract["schema_name"] for contract in contracts])
    stats = collection_obj["stats"]
    if not interfaces.issubset(set(["ERC721", "ERC1155"])):
        raise Exception("We currently do not support non EVM standards at the moment")

    collection = Collection(
        identifier=OpenseaCollectionIdentifier(identifier_type="opensea", slug=collection_slug),
        name=collection_obj["name"],
        chain=Chain.ETH,
        attributes_distribution=collection_obj["traits"],
    )

    collection_with_metadata = CollectionWithMetadata(
        collection=collection,
        contract_addresses=[contract["address"] for contract in contracts],
        token_total_supply=stats["total_supply"],
    )

    return collection_with_metadata

