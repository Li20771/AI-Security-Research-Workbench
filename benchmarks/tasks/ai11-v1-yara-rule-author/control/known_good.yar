/*
 * The declared CORRECT reference rule for ai11-v1-yara-rule-author.
 *
 * It is REFERENCE MATERIAL, not a model output: it exists so the task can prove it is
 * solvable and so the oracle can prove it discriminates (§20.4).
 *
 * It matches each held-out positive and neither held-out negative. The negatives each
 * carry exactly ONE ECU indicator, which is why "2 of them" is required -- a rule that
 * matched a single string would false-positive on holdout_negative_benign.
 */
rule ai11_reference_answer
{
    strings:
        $beacon = "SYNMALWARE_C2_BEACON" ascii
        $url    = "http://syn-c2.invalid/beacon" ascii
        $banner = "SYN-ECU" ascii
        $uds    = "UDS 0x10/0x11/0x22/0x27" ascii
        $ver    = /SYN-ECU v[0-9]+\.[0-9]+/
    condition:
        any of ($beacon, $url) or 2 of ($banner, $uds, $ver)
}
