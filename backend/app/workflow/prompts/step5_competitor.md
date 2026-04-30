Extract product-specific content from the competitor PDP markdown below.

Capture only product-specific content for the EXACT product. If the page is for a different model, voltage, color, size, capacity, or revision, return only `url` and leave other fields empty.

Do NOT include price, stock, shipping, lead time, promo, related products, accessories, substitutes, or cross-sells.

Each spec/feature should record the source as {kind: "competitor", url} so downstream gap validation can count it.
