(function (Jsonary) {
	var knownSchemaKeys = ["title", "description", "type", "enum", "default", "allOf", "anyOf", "oneOf", "not", "multipleOf", "maximum", "exclusiveMaximum", "minimum", "exclusiveMinimum", "maxLength", "minLength", "pattern", "required", "properties", "patternProperties", "additionalProperties", "minProperties", "maxProperties", "dependencies", "items", "additionalItems", "maxItems", "minItems", "uniqueItems", "definitions"];
	
	Jsonary.render.register({
		tabs: {
			all: {
				title: "Univeral constraints",
				renderHtml: function (data, context) {
					var result = "";
					if (!data.readOnly() || data.property("enum").defined()) {
						result += '<h2>Enum values:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("enum")) + '</div>';
					}
					if (!data.readOnly() || data.property("default").defined()) {
						result += '<h2>Default value:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("default")) + '</div>';
					}
					if (!data.readOnly() || data.property("allOf").defined()) {
						result += '<h2>All of (extends):</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("allOf")) + '</div>';
					}
					if (!data.readOnly() || data.property("anyOf").defined()) {
						result += '<h2>At least one of:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("anyOf")) + '</div>';
					}
					if (!data.readOnly() || data.property("oneOf").defined()) {
						result += '<h2>Exactly one of:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("oneOf")) + '</div>';
					}
					if (!data.readOnly() || data.property("not").defined()) {
						result += '<h2>Must not be:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("not")) + '</div>';
					}
					return result;
				}
			},
			number: {
				title: "Number",
				renderHtml: function (data, context) {
					var result = "";
					if (!data.readOnly() || data.property("multipleOf").defined()) {
						result += '<h2>Multiple of:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("multipleOf")) + '</div>';
					}
					if (!data.readOnly() || data.property("maximum").defined()) {
						result += '<h2>Maximum:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("maximum")) + '</div>';
						if (data.property("maximum").defined()) {
							result += '<h2>Exlusive maximum:</h2>';
							result += '<div class="section">' + context.renderHtml(data.property("exclusiveMaximum")) + '</div>';
						}
					}
					if (!data.readOnly() || data.property("minimum").defined()) {
						result += '<h2>Minimum:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("minimum")) + '</div>';
						if (data.property("minimum").defined()) {
							result += '<h2>Exlusive minimum:</h2>';
							result += '<div class="section">' + context.renderHtml(data.property("exclusiveMinimum")) + '</div>';
						}
					}
					return result;
				}
			},
			string: {
				title: "String",
				renderHtml: function (data, context) {
					var result = "";
					if (!data.readOnly() || data.property("minLength").defined()) {
						result += '<h2>Minimum length:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("minLength")) + '</div>';
					}
					if (!data.readOnly() || data.property("maxLength").defined()) {
						result += '<h2>Maximum length:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("maxLength")) + '</div>';
					}
					if (!data.readOnly() || data.property("pattern").defined()) {
						result += '<h2>Regular expression pattern:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("pattern")) + '</div>';
					}
					return result;
				}
			},
			object: {
				title: "Object",
				renderHtml: function (data, context) {
					var result = "";
					if (!data.readOnly() || data.property("required").defined()) {
						result += '<h2>Required properties:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("required")) + '</div>';
					}
					result += '<h2>Properties:</h2>';
					result += '<div class="section">' + context.renderHtml(data.property("properties")) + '</div>';
					if (!data.readOnly() || data.property("patternProperties").defined()) {
						result += '<h2>Pattern properties:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("patternProperties")) + '</div>';
					}
					if (!data.readOnly() || data.property("additionalProperties").defined()) {
						result += '<h2>All other properties:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("additionalProperties")) + '</div>';
					}
					if (!data.readOnly() || data.property("minProperties").defined()) {
						result += '<h2>Minimum number of properties:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("minProperties")) + '</div>';
					}
					if (!data.readOnly() || data.property("maxProperties").defined()) {
						result += '<h2>Maximum number of properties:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("maxProperties")) + '</div>';
					}
					if (!data.readOnly() || data.property("dependencies").defined()) {
						result += '<h2>Property dependencies:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("dependencies")) + '</div>';
					}
					return result;
				}
			},
			array: {
				title: "Array",
				renderHtml: function (data, context) {
					var result = "";
					result += '<h2>Items:</h2>';
					result += '<div class="section">' + context.renderHtml(data.property("items")) + '</div>';
					if (data.property("items").basicType() == "array") {
						if (!data.readOnly() || data.property("additionalItems").defined()) {
							result += '<h2>Additional items:</h2>';
							result += '<div class="section">' + context.renderHtml(data.property("additionalItems")) + '</div>';
						}
					}
					if (!data.readOnly() || data.property("maxItems").defined()) {
						result += '<h2>Maximum length:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("maxItems")) + '</div>';
					}
					if (!data.readOnly() || data.property("minItems").defined()) {
						result += '<h2>Minimum length:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("minItems")) + '</div>';
					}
					if (!data.readOnly() || data.property("uniqueItems").defined()) {
						result += '<h2>Unique:</h2>';
						result += '<div class="section">' + context.renderHtml(data.property("uniqueItems")) + '</div>';
					}
					return result;
				}
			},
			definitions: {
				title: "Definitions",
				renderHtml: function (data, context) {
					return context.renderHtml(data.property("definitions"));
				}
			},
			other: {
				title: "Other",
				renderHtml: function (data, context) {
					var result = "";
					data.properties(function (key, subData) {
						if (knownSchemaKeys.indexOf(key) == -1) {
							result += '<h2>' + key + ':</h2>';
							result += '<div class="section">' + context.renderHtml(subData) + '</div>';
						}
					});
					return result;
				}
			}
		},
		tabOrder: ["all", "number", "string", "object", "array", "definitions", "other"],
		renderHtml: function (data, context) {			
			var result = '<div class="json-schema-obj">';
			if (context.uiState.expanded == undefined) {
				context.uiState.expanded = true;
			}
			if (!context.uiState.expanded) {
				result += context.actionHtml('<span class="expand">show</span>', 'expand');
			} else {
				result += context.actionHtml('<span class="expand">hide</span>', 'collapse');
			}
			result += '<h1>';
			if (data.readOnly() && !data.property("title").defined()) {
				result += '(untitled schema)';
			} else {
				result += context.renderHtml(data.property("title"));
			}
			result += '<div style="clear: both"></div></h1>';
			
			if (context.uiState.expanded) {
				result += '<div class="content">';
				
				result += '<div class="section">';
				result += context.renderHtml(data.property("description"));
				result += '</div>';

				if (!data.readOnly()) {
					result += '<div class="section">';
					result += context.actionHtml("Replace with reference", "add-ref");
					result += '</div>';
					if (data.schemas().basicTypes().indexOf("boolean") != -1 || data.parentKey() == "additionalProperties" || data.parentKey() == "additionalItems") {
						result += '<div class="section">';
						result += context.actionHtml("Disallow", "replace-false");
						result += '</div>';
					}
				}

				if (!data.readOnly() || data.property("format").defined()) {
					result += '<h2>Format:</h2>';
					result += '<div class="section">' + context.renderHtml(data.property("format")) + '</div>';
				}
				
				result += '<h2>Type:</h2><div class="section">';
				if (data.readOnly() && !data.property('type').defined()) {
					result += 'Any ';
				}
				result += context.renderHtml(data.property("type"))
				result += '</div>';
				var types = data.property("type").value();
				if (typeof types == "string") {
					types = [types];
				} else if (types == null) {
					types = ["null", "boolean", "number", "string", "object", "array"];
				}
				
				var tabs = {
					all: true,
					definitions: !data.readOnly() || data.property("definitions").defined()
				};
				
				if (types.indexOf('object') != -1) {
					tabs.object = true;
				}
				if (types.indexOf('array') != -1) {
					tabs.array = true;
				}
				if (types.indexOf('number') != -1 || types.indexOf('integer') != -1) {
					tabs.number = true;
				}
				if (types.indexOf('string') != -1) {
					tabs.string = true;
				}
				
				// Tab bar
				result += '<div class="json-schema-tab-bar">';
				var currentTab = null;
				if (context.uiState.currentTab == undefined) {
					context.uiState.currentTab = "all";
				}
				data.properties(function (key, subData) {
					if (knownSchemaKeys.indexOf(key) == -1) {
						tabs.other = true;
					}
				});
				for (var i = 0; i < this.tabOrder.length; i++) {
					var tabKey = this.tabOrder[i];
					var tab = this.tabs[tabKey];
					var subContext = context.subContext();
					if (tabs[tabKey]) {
						if (context.uiState.currentTab == tabKey) {
							result += context.actionHtml('<span class="json-schema-tab-button current">' + tab.title + '</span>', 'select-tab', tabKey);
							currentTab = tab;
						} else {
							result += context.actionHtml('<span class="json-schema-tab-button">' + tab.title + '</span>', 'select-tab', tabKey);
						}
					}
				}
				if (currentTab == null) {
					currentTab = this.tabs.all;
				}
				result += '<div style="clear: both"></div></div><div class="json-schema-tab-content">';
				
				result += currentTab.renderHtml(data, context);
				
				result += '</div></div>';
			}
			
			return result + "</div>";
		},
		action: function (context, actionName, tabKey) {
			if (actionName == "select-tab") {
				context.uiState.currentTab = tabKey;
			} else if (actionName == "add-ref") {
				context.data.property("$ref").setValue("#");
				return false;
			} else if (actionName == "replace-false") {
				context.data.setValue(false);
				return false;
			} else if (actionName == "expand") {
				context.uiState.expanded = true;
			} else {
				context.uiState.expanded = false;
			}
			return true;
		},
		filter: function (data, schemas) {
			return schemas.containsUrl('http://json-schema.org/schema') && data.basicType() == "object";
		},
		update: function (element, data, context, operation) {
			if (operation.hasPrefix(data.property("type").pointerPath())) {
				return true;
			}
			return this.defaultUpdate(element, data, context, operation);
		}
	});

	Jsonary.render.register({
		renderHtml: function (data, context) {			
			var result = '<div class="json-schema-boolean">';
			if (data.value()) {
				result += 'Anything';
			} else {
				result += 'Not allowed';
			}
			if (!data.readOnly()) {
				result += " (" + context.actionHtml("replace with schema", "replace-schema") + ")";
			}
			return result + '</div>';
		},
		action: function (context, actionName) {
			var data = context.data;
			if (actionName == "replace-schema") {
				data.setValue({});
			}
		},
		filter: function (data, schemas) {
			return schemas.containsUrl('http://json-schema.org/schema') && data.basicType() == "boolean";
		}
	});

	Jsonary.render.register({
		enhance: function (element, data, context) {
			var previewElement = document.createElement("div");
			element.appendChild(previewElement);
			var fullLink = data.links("full")[0];
			fullLink.follow(function (link, submissionData, request) {
				request.getData(function (data) {
					var result = '<div class="json-schema-obj">';
					if (!data.property("title").defined()) {
						result += '<h1>(untitled schema)</h1>';
					} else {
						result += '<h1>' + data.propertyValue("title") + '</h1>';
					}
					result += '<div style="clear: both"></div></h1>';
					previewElement.innerHTML = result;
				});
				return false;
			});
			element = null;
		},
		renderHtml: function (data, context) {			
			var result = '<div class="json-schema-ref">';
			result += context.actionHtml("Reference", "follow");
			result += ": " + context.renderHtml(data.property("$ref"));
			return result + "</div>";
		},
		action: function (context, actionName) {
			var data = context.data;
			if (actionName == "follow") {
				var fullLink = data.links('full')[0];
				fullLink.follow();
			}
		},
		filter: function (data, schemas) {
			return schemas.containsUrl('http://json-schema.org/schema') && data.property("$ref").defined();
		}
	});
	
	Jsonary.addToCache("http://json-schema.org/schema", {
		"title": "JSON Schema",
		"type": "object",
		"properties": {
			"type": {
				"title": "Types",
				"oneOf": [
					{
						"type": "array",
						"items": {
							"type": "string",
							"enum": ["null", "boolean", "integer", "number", "string", "object", "array"],
						},
						"uniqueItems": true
					},
					{
						"type": "string",
						"enum": ["null", "boolean", "integer", "number", "string", "object", "array"]
					}
				]
			},
			"title": {
				"title": "Schema title",
				"type": "string"
			},
			"description": {
				"title": "Schema description",
				"type": "string"
			},
			"oneOf": {
				"title": "One-Of",
				"description": "Instances must match exactly one of the schemas in this property",
				"type": "array",
				"items": {"$ref": "#"}
			},
			"anyOf": {
				"title": "Any-Of",
				"description": "Instances must match at least one of the schemas in this property",
				"type": "array",
				"items": {"$ref": "#"}
			},
			"allOf": {
				"title": "All-Of",
				"description": "Instances must match all of the schemas in this property",
				"type": "array",
				"items": {"$ref": "#"}
			},
			"extends": {
				"title": "Extends (DEPRECATED)",
				"description": "Instances must match all of the schemas in this property",
				"type": "array",
				"items": {"$ref": "#"}
			},
			"enum": {
				"title": "Enum values",
				"description": "If defined, then the value must be equal to one of the items in this array",
				"type": "array"
			},
			"default": {
				"title": "Default value",
				"type": "any"
			},
			"properties": {
				"title": "Object properties",
				"type": "object",
				"additionalProperties": {"$ref": "#"}
			},
			"required": {
				"title": "Required properties",
				"description": "If the instance is an object, these properties must be present",
				"type": "array",
				"items": {
					"title": "Property name",
					"type": "string"
				}
			},
			"dependencies": {
				"title": "Dependencies",
				"description": "If the instance is an object, and contains a property matching one of those here, then it must also follow the corresponding schema",
				"type": "object",
				"additionalProperties": {"$ref": "#"}
			},
			"additionalProperties": {
				"oneOf": [
					{"$ref": "#"},
					{"type": "boolean"}
				]
			},
			"items": {
				"title": "Array items",
				"oneOf": [
					{"$ref": "#"},
					{
						"title": "Tuple type",
						"type": "array",
						"minItems": 1,
						"items": {"$ref": "#"}
					}
				]
			},
			"additionalItems": {"$ref": "#"},
			"minItems": {
				"title": "Minimum array length",
				"type": "integer",
				"minimum": 0
			},
			"maxItems": {
				"title": "Maximum array length",
				"type": "integer",
				"minimum": 0
			},
			"uniqueItems": {
				"title": "Unique items",
				"description": "If set to true, and the value is an array, then no two items in the array should be equal.",
				"type": "boolean",
				"default": false
			},
			"pattern": {
				"title": "Regular expression",
				"description": "An regular expression (ECMA 262) which the value must match if it's a string",
				"type": "string",
				"format": "regex"
			},
			"minLength": {
				"title": "Minimum string length",
				"type": "integer",
				"minimum": 0,
				"default": 0
			},
			"maxLength": {
				"title": "Maximum string length",
				"type": "integer",
				"minimum": 0
			},
			"minimum": {
				"title": "Minimum value",
				"type": "number"
			},
			"maximum": {
				"title": "Maximum value",
				"type": "number"
			},
			"exclusiveMinimum": {
				"title": "Exclusive Minimum",
				"description": "If the value is a number and this is set to true, then the value cannot be equal to the value specified in \"minimum\"",
				"type": "boolean",
				"default": false
			},
			"exclusiveMaximum": {
				"title": "Exclusive Maximum",
				"description": "If the value is a number and this is set to true, then the value cannot be equal to the value specified in \"maximum\"",
				"type": "boolean",
				"default": false
			},
			"divisibleBy": {
				"title": "Divisible by",
				"description": "If the value is a number, then it must be an integer multiple of the value of this property",
				"type": "number",
				"minimum": 0,
				"exclusiveMinimum": true
			},
			"$ref": {
				"title": "Reference URI",
				"description": "This contains the URI of a schema, which should be used to replace the containing schema.",
				"type": "string",
				"format": "uri"
			}
		},
		"additionalProperties": {},
		"links": [
			{
				"href": "{+($ref)}",
				"rel": "full"
			}
		]
	}, "http://json-schema.org/schema");

	Jsonary.addToCache("http://json-schema.org/hyper-schema", {
		"allOf": [
			{"$ref": "http://json-schema.org/schema"}
		]
	}, "http://json-schema.org/hyper-schema");
})(Jsonary);
