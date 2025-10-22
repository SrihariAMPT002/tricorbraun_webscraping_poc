import tldextract
berlin_packing = 'https://www.berlinpackaging.com/'
cary_company = 'https://www.thecarycompany.com/'
ext = tldextract.extract(cary_company)
print(ext.top_domain_under_public_suffix)
