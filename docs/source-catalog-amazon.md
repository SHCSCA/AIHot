# Amazon Source Expansion Catalog

## Scope

`channels/catalogs/amazon_expansion.yaml` is a reviewed expansion catalog for the
Amazon seller intelligence channel. It adds 220 enabled, collectable endpoints
to the 105 currently enabled and collectable endpoints in `channels/amazon.yaml`.
The catalog therefore provides 325 unique endpoints at the inventory level.

This is an active production catalog:

- `channels/amazon.yaml` references it through `source_catalogs`; the loader
  merges it without recursively treating catalog files as channels.
- Every expansion item omits `crawl_interval_minutes` and inherits the single
  project-wide schedule from `config/collection.yaml`.
- Deployment seeds the merged catalog into the source registry.

## Catalog Contract

Every source contains the existing source identity and collection fields:

- `id`, `source_type`, `name`, `url`
- `language`, `region`, `marketplace`, `seller_area`
- `trust_level`, `base_weight`, `default_categories`
- `parser_type`, `enabled`
- `publisher_key`, `source_group`
- `collection_status: collectable`, `free_access: true`

Only parser types already mapped to working fetch adapters are allowed:

| Catalog parser | Runtime adapter |
| --- | --- |
| `rss` | `RssFetchAdapter` |
| `atom` | `RssFetchAdapter` via `source_seed._fetch_adapter` |
| `html_list` | `HtmlListAdapter` |
| `aihot_api` | `AihotApiAdapter` |

The expansion currently uses RSS and Atom only. This avoids treating an
arbitrary web page as collectable when the generic HTML list parser cannot
reliably find dated article blocks.

## Coverage

### Endpoint totals

| Scope | Enabled and collectable endpoints |
| --- | ---: |
| Existing Amazon channel | 105 |
| Expansion catalog | 220 |
| Combined inventory | 325 |

### Expansion parser distribution

| Parser | Endpoints |
| --- | ---: |
| Atom | 184 |
| RSS | 36 |

The Atom group contains 180 repository release feeds and four GOV.UK
organization feeds. The RSS group contains official, regulatory, ecommerce,
seller-service, advertising, tax, logistics, and retail-media feeds.

### Expansion source-group distribution

| Source group | Endpoints |
| --- | ---: |
| Vendor release | 101 |
| Ecosystem release | 73 |
| Vendor editorial feed | 22 |
| Media | 10 |
| Official | 6 |
| Official repository | 6 |
| First-party ecosystem | 1 |
| Expert | 1 |

### Expansion trust distribution

| Trust level | Endpoints |
| --- | ---: |
| Authority | 125 |
| Expert | 73 |
| Official | 12 |
| Media | 10 |

### Seller-area distribution

| Seller area | Endpoints |
| --- | ---: |
| Tools | 64 |
| Payments / margin systems | 48 |
| Amazon and marketplace integrations | 40 |
| Operations | 17 |
| Logistics / fulfillment | 14 |
| Compliance / tax / trade / brand protection | 12 |
| Ads / marketing | 8 |
| Catalog / listing | 6 |
| Industry / policy | 6 |
| Sourcing / research / marketplaces | 5 |

The expansion contains 126 distinct `publisher_key` values. GitHub-backed
publishers are capped at eight endpoints each to prevent one plugin ecosystem
from dominating the catalog. Editorial feeds and repositories owned by the same
publisher share one key (for example, About Amazon and `amzn/*` use `amazon`;
the WooCommerce blog and `woocommerce/*` use `woocommerce`).

### Category-tag distribution

Category tags are multi-valued, so totals exceed 220:

| Category | Tagged endpoints |
| --- | ---: |
| Tools | 192 |
| Product research | 78 |
| Fees / margin | 70 |
| Policy | 45 |
| FBA / logistics | 29 |
| Listing / SEO | 23 |
| Compliance / trade | 19 |
| Ads / PPC | 12 |
| Account health | 1 |

### Required-domain coverage

| Domain | Representative combined sources |
| --- | --- |
| Amazon official / Seller Central | Existing Seller blog and SP-API release notes; About Amazon; official `amzn` SP-API, Amazon Pay, and Marketing Stream releases |
| Regional policy | GOV.UK HMRC, Business and Trade, CMA, IPO; European Commission Press Corner |
| FBA / logistics | Existing Amazon Shipping; Supply Chain Dive, FreightWaves, DCL Logistics, ZhenHub, SupplyChainBrain |
| Advertising / PPC | Adverio, Feedvisor, Amazon Marketing Stream, ecommerce marketing feeds |
| Tax / trade compliance | HMRC, European Commission, hellotax, cross-border commerce sources |
| Retail / ecommerce media | Ecommerce News Europe, E-Commerce Nation, Internet Retailing Australia, Supply Chain 24/7 |
| Seller tools / service providers | Amazon SP-API clients, marketplace connectors, catalog/PIM, inventory, payment, fulfillment, and commerce-platform release feeds |

## Validation Method

Validation was performed on 2026-07-28 with network access.

1. Existing eligible sources were counted using the production criteria:
   `enabled`, `collection_status == collectable`, and a currently supported
   parser.
2. Candidate URLs were normalized and compared with every URL and ID already
   present in `channels/amazon.yaml`.
3. Direct RSS/Atom candidates were fetched with redirects enabled and parsed
   with the project's installed `feedparser`.
4. A direct feed was retained only when it returned a successful document,
   contained entries, and at least one of the first ten entries had a published
   or updated timestamp.
5. GitHub candidates were discovered from real repositories. A release endpoint
   was retained only when `/releases.atom` returned a non-empty Atom feed with a
   dated release entry. Selected repositories had a latest release in 2023 or
   later.
6. Search-result pages, Google/Bing News queries, generated RSS services,
   duplicate URLs, empty release feeds, archived repositories, tutorial
   repositories, and query-parameter feed variants used only to inflate the
   count were excluded.
7. The final generated catalog was fetched again in full: all 220 endpoints
   returned a parseable, non-empty feed with dated entries.

The live checks establish endpoint and feed-level collectability at catalog
creation time. They are not a guarantee that all publishers will remain
available or publish within every Amazon rolling window. The catalog has not
been replayed end to end through job scheduling, normalization, clustering, and
review because loading the nested catalog requires a separate integration
change.

## Cross-Validation Readiness

`publisher_key` is the independence boundary for corroboration. Multiple feeds
owned by the same publisher must count as one publisher, even when their URLs
or repositories differ. `source_group` separates official, vendor, media, and
ecosystem signals.

A future corroboration rule can require:

- at least two distinct `publisher_key` values for a corroborated claim;
- at least one official or authority source for policy, fee, tax, or compliance
  conclusions;
- repository releases to support product-change evidence, but not to
  independently confirm a policy interpretation from the same vendor;
- disagreements to remain visible instead of being collapsed into a single
  confident statement.

These fields make the catalog usable by the existing AI analysis stage without
pretending that source volume alone is cross-validation.

## Reproducible Checks

Run schema, uniqueness, parser, and inventory checks:

```powershell
$env:PYTHONPATH = "src"
@'
from pathlib import Path
import yaml

base = yaml.safe_load(Path("channels/amazon.yaml").read_text(encoding="utf-8"))["sources"]
expansion = yaml.safe_load(
    Path("channels/catalogs/amazon_expansion.yaml").read_text(encoding="utf-8")
)["sources"]
supported = {"rss", "atom", "html_list", "aihot_api"}
eligible = [
    source for source in base
    if source.get("enabled")
    and source.get("collection_status", "collectable") == "collectable"
    and source.get("parser_type") in supported
]

assert len(expansion) == 220
assert len(eligible) + len(expansion) >= 320
assert all(source["enabled"] for source in expansion)
assert all(source["collection_status"] == "collectable" for source in expansion)
assert all(source["free_access"] is True for source in expansion)
assert all(source["parser_type"] in supported for source in expansion)
assert all("crawl_interval_minutes" not in source for source in expansion)
assert len({source["id"] for source in expansion}) == len(expansion)
assert len({source["url"].rstrip("/").lower() for source in expansion}) == len(expansion)
assert not ({source["id"] for source in base} & {source["id"] for source in expansion})
assert not (
    {source["url"].rstrip("/").lower() for source in base}
    & {source["url"].rstrip("/").lower() for source in expansion}
)
print({"existing": len(eligible), "expansion": len(expansion), "combined": len(eligible) + len(expansion)})
'@ | .\.venv\Scripts\python.exe -
```

Run the existing fetcher and source-contract tests:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest tests/test_fetchers.py tests/test_sources.py -q
```
