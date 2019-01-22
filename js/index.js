var vegaLite = require('./node_modules/vega-lite/build/vega-lite.js');
var vega = require('./node_modules/vega/build/vega.js');
var tv4 = require('./node_modules/tv4/tv4.js')
var intercept = require("./node_modules/intercept-stdout/intercept-stdout.js")

const exampleSchema = "{\"$schema\":\"https:\/\/vega.github.io\/schema\/vega-lite\/v3.json\",\"description\":\"A simple bar chart with embedded data.\",\"data\":{\"values\":[{\"a\":\"A\",\"b\":28},{\"a\":\"B\",\"b\":55},{\"a\":\"C\",\"b\":43},{\"a\":\"D\",\"b\":91},{\"a\":\"E\",\"b\":81},{\"a\":\"F\",\"b\":53},{\"a\":\"G\",\"b\":19},{\"a\":\"H\",\"b\":87},{\"a\":\"I\",\"b\":52}]},\"mark\":\"bar\",\"encoding\":{\"x\":{\"field\":\"a\"},\"y\":{\"type\":\"quantitative\"}}}"

var targetSpecs = process.argv.slice(2);

result = []
result.push()

for (var i = 0; i < targetSpecs.length; i ++) {
	vlSpec = JSON.parse(targetSpecs[i])
	status = [];
	try {
		var intercept = require("intercept-stdout")
	    
	    var unhook_intercept = intercept(function(txt) {
		    status.push(txt);
		    return "";
		});

		const vgSpec = vegaLite.compile(vlSpec).spec
		const runtime = vega.parse(vgSpec)
		validateResult = tv4.validate(vgSpec, "./node_modules/vega/build/vega-schema.json")

		status.push("Vega validate result: " + validateResult)
		unhook_intercept();

	} catch (err) {
		status.push(err)
	}
	result.push(status)
}

console.log(result)