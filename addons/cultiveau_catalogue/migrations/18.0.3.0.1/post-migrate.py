def migrate(cr, version):
    """Les articles importés avant « Mon catalogue » (référencement, catalogue 3D) sont ceux du catalogue Cultiveau."""
    cr.execute("""UPDATE product_template SET cultiveau_reseau = TRUE
                  WHERE cultiveau_source IN ('matrice', 'catalogue3d') AND company_id IS NULL AND cultiveau_reseau IS NOT TRUE""")
