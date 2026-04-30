Build a JSON-LD Product schema object.

Use ONLY supported values from the verified inputs. Include any of:
- name, brand, manufacturer, mpn, sku, model, category, description
- url (only if subject_url is available)
- image (only if a stable image URL was captured in the subject extract)
- aggregateRating, review (only if visible review data supports it)
- offers (only if price/availability are dynamically maintained — typically OMIT in this app)

Use additionalProperty for important verified attributes from the verified specs list. Each entry should be:
{ "@type": "PropertyValue", "name": "<spec name>", "value": "<value with unit if applicable>" }

Prefer including additionalProperty entries for: Voltage, Current, Power, Input voltage, Frequency, Efficiency, Dimensions, Weight, Mounting style, Connector type, Operating temperature, Cooling method, Protection functions, Certifications, Warranty.

Do NOT create fake ratings, reviews, prices, availability, images, or unsupported claims. Omit any field you cannot verify.

Return a single JSON object (no wrapper). It must include "@context": "https://schema.org" and "@type": "Product".
