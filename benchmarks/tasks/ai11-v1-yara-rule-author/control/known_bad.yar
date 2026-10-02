/*
 * The declared INCORRECT reference rule. It is the discrimination control (§7.4).
 *
 * It is not a syntax error -- it compiles and runs. It is WRONG: it matches on a single
 * weak indicator, so it fires on holdout_negative_clean (which contains "AFL" as an
 * ordinary word) and produces a false positive. An oracle that could not tell this rule
 * from the one above would be an oracle that cannot fail.
 */
rule ai11_reference_false_positive
{
    strings:
        $weak = "AFL" ascii
    condition:
        $weak
}
