#!/usr/bin/env node
process.env.FUSION_ROLE = "cua";
require("./_python.js")("openfusion.delegate");
