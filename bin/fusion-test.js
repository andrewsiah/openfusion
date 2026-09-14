#!/usr/bin/env node
process.env.FUSION_ROLE = "tester";
require("./_python.js")("openfusion.delegate");
