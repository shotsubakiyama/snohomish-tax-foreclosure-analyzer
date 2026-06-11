# Machine-Readable Parser Version 3

Version 3 prevents referenced parcel numbers inside legal descriptions and
special-condition notes from being mistaken for new source records.

A source record must now begin with an explicit marker such as:

- `#131 30051200201100`
- `APN: 00373300800400`

Page-spanning records remain valid records and are tracked by
`record_spans_pages_flag`; they are no longer sent to the review queue solely
because they cross a page boundary.
