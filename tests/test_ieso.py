from services.ieso import parse_day_ahead_price_xml, parse_demand_csv, parse_realtime_price_xml


def test_demand_parser_handles_ieso_preamble():
    text = """\\Hourly Demand Report
Date,Hour,Market Demand,Ontario Demand
2026-08-14,1,15000,14500
2026-08-14,2,14900,14400
"""
    rows = parse_demand_csv(text)
    assert len(rows) == 2
    assert rows[-1].ontario_demand_mw == 14400


def test_day_ahead_parser():
    xml = """<Document xmlns="http://www.ieso.ca/schema"><DocBody><DeliveryDate>2026-08-16</DeliveryDate>
    <HourlyPriceComponents><PricingHour>1</PricingHour><ZonalPrice>22.5</ZonalPrice><LossPriceCapped>1.1</LossPriceCapped><CongestionPriceCapped>0.2</CongestionPriceCapped></HourlyPriceComponents>
    <HourlyPriceComponents><PricingHour>2</PricingHour><ZonalPrice>30.0</ZonalPrice><LossPriceCapped>1.2</LossPriceCapped><CongestionPriceCapped>0.3</CongestionPriceCapped></HourlyPriceComponents>
    </DocBody></Document>"""
    parsed = parse_day_ahead_price_xml(xml)
    assert parsed["delivery_date"] == "2026-08-16"
    assert parsed["hours"][1]["price"] == 30.0


def test_realtime_parser():
    xml = """<Document xmlns="http://www.ieso.ca/schema"><DocBody><DeliveryHour>15</DeliveryHour>
    <ZonalPrice><Interval>1</Interval><LmpCap>44.2</LmpCap><LossPriceCap>1.2</LossPriceCap><CongPriceCap>0.5</CongPriceCap></ZonalPrice>
    <ZonalPrice><Interval>2</Interval><LmpCap>48.9</LmpCap><LossPriceCap>1.3</LossPriceCap><CongPriceCap>0.7</CongPriceCap></ZonalPrice>
    </DocBody></Document>"""
    parsed = parse_realtime_price_xml(xml)
    assert parsed["delivery_hour"] == 15
    assert parsed["price"] == 48.9
