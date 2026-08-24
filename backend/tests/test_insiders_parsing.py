from app.fetchers.insiders import _resolve_xml_href, parse_form4_xml


class TestResolveXmlHref:
    def test_root_relative_href_joins_against_host_only(self):
        # This is the exact bug confirmed live: joining a root-relative
        # href against the index page's directory produced a duplicated
        # path and 404s on every single market-wide filing.
        result = _resolve_xml_href(
            "/Archives/edgar/data/1857816/000162828026058507/xslF345X06/wk-form4_1787363036.xml",
            "https://www.sec.gov/Archives/edgar/data/2004307/000162828026058507/0001628280-26-058507-index.htm",
            "www.sec.gov",
        )
        assert result == "https://www.sec.gov/Archives/edgar/data/1857816/000162828026058507/xslF345X06/wk-form4_1787363036.xml"
        assert result.count("Archives/edgar/data") == 1  # no duplication

    def test_absolute_href_passed_through(self):
        result = _resolve_xml_href(
            "https://www.sec.gov/Archives/edgar/data/1/2/form.xml",
            "https://www.sec.gov/Archives/edgar/data/1/2/index.htm",
            "www.sec.gov",
        )
        assert result == "https://www.sec.gov/Archives/edgar/data/1/2/form.xml"

    def test_page_relative_href_joins_against_page_directory(self):
        result = _resolve_xml_href(
            "form.xml",
            "https://www.sec.gov/Archives/edgar/data/1/2/index.htm",
            "www.sec.gov",
        )
        assert result == "https://www.sec.gov/Archives/edgar/data/1/2/form.xml"


class TestParseForm4Xml:
    def test_parses_real_non_derivative_transaction(self):
        # Based on a real, publicly filed Form 4's structure (PartnerRe,
        # CIK 911421) -- the schema fields this asserts on are the
        # documented EDGAR ownership XML fields, not invented ones.
        xml = b"""<?xml version="1.0"?>
        <ownershipDocument>
            <periodOfReport>2011-12-02</periodOfReport>
            <issuer>
                <issuerCik>0000911421</issuerCik>
                <issuerName>PARTNERRE LTD</issuerName>
                <issuerTradingSymbol>PRE</issuerTradingSymbol>
            </issuer>
            <reportingOwner>
                <reportingOwnerId>
                    <rptOwnerName>ROLLWAGEN JOHN A</rptOwnerName>
                </reportingOwnerId>
                <reportingOwnerRelationship>
                    <isDirector>1</isDirector>
                </reportingOwnerRelationship>
            </reportingOwner>
            <nonDerivativeTable>
                <nonDerivativeTransaction>
                    <transactionDate><value>2011-12-02</value></transactionDate>
                    <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
                    <transactionAmounts>
                        <transactionShares><value>500</value></transactionShares>
                        <transactionPricePerShare><value>75.00</value></transactionPricePerShare>
                    </transactionAmounts>
                </nonDerivativeTransaction>
            </nonDerivativeTable>
        </ownershipDocument>"""
        result = parse_form4_xml(xml, source_url="https://example.com/form.xml")
        assert result is not None
        assert result["ticker"] == "PRE"
        assert result["insider_name"] == "ROLLWAGEN JOHN A"
        assert result["transaction"] == "buy"
        assert result["shares"] == 500
        assert result["value_usd"] == 37500.0
        assert result["insider_role"] == "Director"

    def test_derivative_only_filing_is_skipped_not_misrepresented(self):
        xml = b"""<?xml version="1.0"?>
        <ownershipDocument>
            <issuer>
                <issuerTradingSymbol>PRE</issuerTradingSymbol>
                <issuerName>PARTNERRE LTD</issuerName>
            </issuer>
            <reportingOwner>
                <reportingOwnerId><rptOwnerName>SOMEONE</rptOwnerName></reportingOwnerId>
            </reportingOwner>
            <derivativeTable>
                <derivativeTransaction></derivativeTransaction>
            </derivativeTable>
        </ownershipDocument>"""
        assert parse_form4_xml(xml, source_url="https://example.com/form.xml") is None

    def test_malformed_xml_returns_none_not_exception(self):
        assert parse_form4_xml(b"not xml at all", source_url="x") is None
