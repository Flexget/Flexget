(function () {
	function escapeHtml(text) {
		return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
	}
	if (window.escapeHtml == undefined) {
		window.escapeHtml = escapeHtml;
	}

	Jsonary.render.register({
		component: Jsonary.render.Components.ADD_REMOVE,
		renderHtml: function (data, context) {
			if (!data.defined()) {
				context.uiState.undefined = true;
				return context.actionHtml('<span class="json-undefined-create">+ create</span>', "create");
			}
			delete context.uiState.undefined;
			var showDelete = false;
			if (data.parent() != null) {
				var parent = data.parent();
				if (parent.basicType() == "object") {
					var required = parent.schemas().requiredProperties();
					var minProperties = parent.schemas().minProperties();
					showDelete = required.indexOf(data.parentKey()) == -1 && parent.keys().length > minProperties;
				} else if (parent.basicType() == "array") {
					var tupleTypingLength = parent.schemas().tupleTypingLength();
					var minItems = parent.schemas().minItems();
					var index = parseInt(data.parentKey());
					if ((index >= tupleTypingLength || index == parent.length() - 1)
						&& parent.length() > minItems) {
						showDelete = true;
					}
				}
			}
			var result = "";
			if (showDelete) {
				result += "<div class='json-object-delete-container'>";
				result += context.actionHtml("<span class='json-object-delete'>X</span>", "remove") + " ";
				result += context.renderHtml(data);
				result += '<div style="clear: both"></div></div>';
			} else {
				result += context.renderHtml(data);
			}
			return result;
		},
		action: function (context, actionName) {
			if (actionName == "create") {
				var data = context.data;
				var parent = data.parent();
				var finalComponent = data.parentKey();
				if (parent != undefined) {
					var parentSchemas = parent.schemas();
					if (parent.basicType() == "array") {
						parentSchemas.createValueForIndex(finalComponent, function (newValue) {
							parent.index(finalComponent).setValue(newValue);
						});
					} else {
						if (parent.basicType() != "object") {
							parent.setValue({});
						}
						parentSchemas.createValueForProperty(finalComponent, function (newValue) {
							parent.property(finalComponent).setValue(newValue);
						});
					}
				} else {
					data.schemas().createValue(function (newValue) {
						data.setValue(newValue);
					});
				}
			} else if (actionName == "remove") {
				context.data.remove();
			} else {
				alert("Unkown action: " + actionName);
			}
		},
		update: function (element, data, context, operation) {
			return context.uiState.undefined;
		},
		filter: function (data) {
			return !data.readOnly();
		}
	});

	Jsonary.render.register({
		component: Jsonary.render.Components.TYPE_SELECTOR,
		renderHtml: function (data, context) {
			var result = "";
			var basicTypes = data.schemas().basicTypes();
			var enums = data.schemas().enumValues();
			if (context.uiState.dialogOpen) {
				result += '<div class="json-select-type-dialog-outer"><span class="json-select-type-dialog">';
				result += context.actionHtml('close', "closeDialog");
				if (basicTypes.length > 1) {
					result += '<br>Select basic type:<ul>';
					for (var i = 0; i < basicTypes.length; i++) {
						if (basicTypes[i] == "integer" && basicTypes.indexOf("number") != -1) {
							continue;
						}
						if (basicTypes[i] == data.basicType() || basicTypes[i] == "number" && data.basicType() == "integer") {
							result += '<li>' + basicTypes[i];
						} else {
							result += '<li>' + context.actionHtml(basicTypes[i], 'select-basic-type', basicTypes[i]);
						}
					}
					result += '</ul>';
				}
				result += '</span></div>';
			}
			if (basicTypes.length > 1 && enums == null) {
				result += context.actionHtml("<span class=\"json-select-type\">T</span>", "openDialog") + " ";
			}
			result += context.renderHtml(data);
			return result;
		},
		action: function (context, actionName, basicType) {
			if (actionName == "closeDialog") {
				context.uiState.dialogOpen = false;
				return true;
			} else if (actionName == "openDialog") {
				context.uiState.dialogOpen = true;
				return true;
			} else if (actionName == "select-basic-type") {
				context.uiState.dialogOpen = false;
				var schemas = context.data.schemas().concat([Jsonary.createSchema({type: basicType})]);
				schemas.createValue(function (newValue) {
					context.data.setValue(newValue);
				});
				return true;
			} else {
				alert("Unkown action: " + actionName);
			}
		},
		update: function (element, data, context, operation) {
			return false;
		},
		filter: function (data) {
			return !data.readOnly();
		}
	});

	// Display schema switcher
	Jsonary.render.Components.add("SCHEMA_SWITCHER");
	Jsonary.render.register({
		component: Jsonary.render.Components.SCHEMA_SWITCHER,
		renderHtml: function (data, context) {
			var result = "";
			var fixedSchemas = data.schemas().fixed();

			context.uiState.xorSelected = [];
			context.uiState.orSelected = [];
			if (context.uiState.dialogOpen) {
				result += '<div class="json-select-type-dialog-outer"><span class="json-select-type-dialog">';
				result += context.actionHtml('close', "closeDialog");
				var xorSchemas = fixedSchemas.xorSchemas();
				for (var i = 0; i < xorSchemas.length; i++) {
					var options = xorSchemas[i];
					var inputName = context.inputNameForAction('selectXorSchema', i);
					result += '<br><select name="' + inputName + '">';
					for (var j = 0; j < options.length; j++) {
						var schema = options[j];
						schema.getFull(function (s) {schema = s;});
						var selected = "";
						if (data.schemas().indexOf(schema) != -1) {
							context.uiState.xorSelected[i] = j;
							selected = " selected";
						}
						result += '<option value="' + j + '"' + selected + '>' + schema.title() + '</option>'
					}
					result += '</select>';
				}
				var orSchemas = fixedSchemas.orSchemas();
				for (var i = 0; i < orSchemas.length; i++) {
					var options = orSchemas[i];
					var inputName = context.inputNameForAction('selectOrSchema', i);
					result += '<br><select name="' + inputName + '" multiple size="' + options.length + '">';
					context.uiState.orSelected[i] = [];
					for (var j = 0; j < options.length; j++) {
						var schema = options[j];
						schema.getFull(function (s) {schema = s;});
						var selected = "";
						if (data.schemas().indexOf(schema) != -1) {
							context.uiState.orSelected[i][j] = true;
							selected = " selected";
						} else {
							context.uiState.orSelected[i][j] = false;
						}
						result += '<option value="' + j + '"' + selected + '>' + schema.title() + '</option>'
					}
					result += '</select>';
				}
				result += '</span></div>';
			}
			if (fixedSchemas.length < data.schemas().length) {
				result += context.actionHtml("<span class=\"json-select-type\">S</span>", "openDialog") + " ";
			}
			result += context.renderHtml(data);
			return result;
		},
		createValue: function (context) {
			var data = context.data;
			var newSchemas = context.data.schemas().fixed();
			var xorSchemas = context.data.schemas().fixed().xorSchemas();
			for (var i = 0; i < xorSchemas.length; i++) {
				newSchemas = newSchemas.concat([xorSchemas[i][context.uiState.xorSelected[i]]]);
			}
			var orSchemas = context.data.schemas().fixed().orSchemas();
			for (var i = 0; i < orSchemas.length; i++) {
				var options = orSchemas[i];
				for (var j = 0; j < options.length; j++) {
					if (context.uiState.orSelected[i][j]) {
						newSchemas = newSchemas.concat([options[j]]);
					}
				}
			}
			newSchemas.getFull(function (sl) {newSchemas = sl;});
			data.setValue(newSchemas.createValue());
		},
		action: function (context, actionName, value, arg1) {
			if (actionName == "closeDialog") {
				context.uiState.dialogOpen = false;
				return true;
			} else if (actionName == "openDialog") {
				context.uiState.dialogOpen = true;
				return true;
			} else if (actionName == "selectXorSchema") {
				context.uiState.xorSelected[arg1] = value;
				this.createValue(context);
				return true;
			} else if (actionName == "selectOrSchema") {
				context.uiState.orSelected[arg1] = [];
				for (var i = 0; i < value.length; i++) {
					context.uiState.orSelected[arg1][value[i]] = true;
				}
				this.createValue(context);
				return true;
			} else {
				alert("Unkown action: " + actionName);
			}
		},
		update: function (element, data, context, operation) {
			return false;
		},
		filter: function (data) {
			return !data.readOnly();
		}
	});

	// Display raw JSON
	Jsonary.render.register({
		renderHtml: function (data, context) {
			if (!data.defined()) {
				return "";
			}
			return '<span class="json-raw">' + escapeHtml(JSON.stringify(data.value())) + '</span>';
		},
		filter: function (data) {
			return true;
		}
	});

	function updateTextAreaSize(textarea) {
		var lines = textarea.value.split("\n");
		var maxWidth = 4;
		for (var i = 0; i < lines.length; i++) {
			if (maxWidth < lines[i].length) {
				maxWidth = lines[i].length;
			}
		}
		textarea.setAttribute("cols", maxWidth + 1);
		textarea.setAttribute("rows", lines.length);
	}

	// Display/edit objects
	Jsonary.render.register({
		renderHtml: function (data, context) {
			var uiState = context.uiState;
			var result = '<table class="json-object"><tbody>';
			data.properties(function (key, subData) {
				result += '<tr>';
				result +=	'<td class="json-object-key"><div class="json-object-key-text">' + context.actionHtml(escapeHtml(key), "expand-contract") + ':</div></td>';
                if (subData.basicType() == "array" || (subData.basicType() == "object")) {
                    result += '<td></td></tr><tr><td class="json-object-value-row", colspan="2">'
                } else {
                    result += '<td class="json-object-value">'
                }
				result +=    context.renderHtml(subData) + '</td>';
				result += '</tr>';
			});
			result += '</tbody></table>';
			if (!data.readOnly()) {
				var schemas = data.schemas();
				var maxProperties = schemas.maxProperties();
				if (maxProperties == null || maxProperties > data.keys().length) {
					var addLinkHtml = "";
					var definedProperties = schemas.definedProperties().sort();
					var keyFunction = function (index, key) {
						var addHtml = '<span class="json-object-add-key">' + escapeHtml(key) + '</span>';
						addLinkHtml += context.actionHtml(addHtml, "add-named", key);
					};
					for (var i = 0; i < definedProperties.length; i++) {
						if (!data.property(definedProperties[i]).defined()) {
							keyFunction(i, definedProperties[i]);
						}
					}
					if (schemas.allowedAdditionalProperties()) {
						var newHtml = '<span class="json-object-add-key-new">+ new</span>';
						addLinkHtml += context.actionHtml(newHtml, "add-new");
					}
					if (addLinkHtml != "") {
						result += 'add: <span class="json-object-add">' + addLinkHtml + '</span>';
					}
				}
			}
			return result;
		},
		action: function (context, actionName, arg1) {
			var data = context.data;
			if (actionName == "add-named") {
				var key = arg1;
				data.schemas().createValueForProperty(key, function (newValue) {
					data.property(key).setValue(newValue);
				});
			} else if (actionName == "add-new") {
				var key = window.prompt("New key:", "key");
				if (key != null && !data.property(key).defined()) {
					data.schemas().createValueForProperty(key, function (newValue) {
						data.property(key).setValue(newValue);
					});
				}
			} else if (actionName == "expand-contract") {

            }
		},
		filter: function (data) {
			return data.basicType() == "object";
		}
	});

	// Display/edit arrays
	Jsonary.render.register({
		renderHtml: function (data, context) {
			var tupleTypingLength = data.schemas().tupleTypingLength();
			var maxItems = data.schemas().maxItems();
			var result = "<table>";
			data.indices(function (index, subData) {
				result += '<tr class="json-array-item">';
				result += '<td class="json-array-value-prefix">- </td>'
                result += '<td class="json-array-value">' + context.renderHtml(subData) + '</td>';
				result += '</tr>';
			});
			if (!data.readOnly()) {
				if (maxItems == null || data.length() < maxItems) {
                    result += '<tr><td>'
					var addHtml = '<span class="json-array-add">+ add</span>';
					result += context.actionHtml(addHtml, "add") + "</td></tr>";
				}
			}
			return result + "</table>";
		},
		action: function (context, actionName) {
			var data = context.data;
			if (actionName == "add") {
				var index = data.length();
				data.schemas().createValueForIndex(index, function (newValue) {
					data.index(index).setValue(newValue);
				});
			}
		},
		filter: function (data) {
			return data.basicType() == "array";
		}
	});

	// Display string
	Jsonary.render.register({
		renderHtml: function (data, context) {
			return '<span class="json-string">' + escapeHtml(data.value()) + '</span>';
		},
		filter: function (data) {
			return data.basicType() == "string" && data.readOnly();
		}
	});

	// Display string
	Jsonary.render.register({
		renderHtml: function (data, context) {
			var date = new Date(data.value());
			return '<span class="json-string json-string-date">' + date.toLocaleString() + '</span>';
		},
		filter: function (data, schemas) {
			return data.basicType() == "string" && data.readOnly() && schemas.formats().indexOf("date-time") != -1;
		}
	});

	function copyTextStyle(source, target) {
		var style = getComputedStyle(source, null);
		for (var key in style) {
			if (key.substring(0, 4) == "font" || key.substring(0, 4) == "text") {
				target.style[key] = style[key];
			}
		}
	}
	function updateTextareaSize(textarea, sizeMatchBox, suffix) {
		sizeMatchBox.innerHTML = "";
		sizeMatchBox.appendChild(document.createTextNode(textarea.value + suffix));
		var style = getComputedStyle(sizeMatchBox, null);
		textarea.style.width = parseInt(style.width.substring(0, style.width.length - 2)) + 4 + "px";
		textarea.style.height = parseInt(style.height.substring(0, style.height.length - 2)) + 4 + "px";
	}

	function getText(element) {
		var result = "";
		for (var i = 0; i < element.childNodes.length; i++) {
			var child = element.childNodes[i];
			if (child.nodeType == 1) {
				var tagName = child.tagName.toLowerCase();
				if (tagName == "br") {
					result += "\n";
					continue;
				}
				if (child.tagName == "li") {
					result += "\n*\t";
				}
				if (tagName == "p"
					|| /^h[0-6]$/.test(tagName)
					|| tagName == "header"
					|| tagName == "aside"
					|| tagName == "blockquote"
					|| tagName == "footer"
					|| tagName == "div"
					|| tagName == "table"
					|| tagName == "hr") {
					if (result != "") {
						result += "\n";
					}
				}
				if (tagName == "td" || tagName == "th") {
					result += "\t";
				}

				result += getText(child);

				if (tagName == "tr") {
					result += "\n";
				}
			} else if (child.nodeType == 3) {
				result += child.nodeValue;
			}
		}
		result = result.replace("\r\n", "\n");
		return result;
	}

	// Edit string
	Jsonary.render.register({
		renderHtml: function (data, context) {
			var maxLength = data.schemas().maxLength();
			var inputName = context.inputNameForAction('new-value');
			var valueHtml = escapeHtml(data.value()).replace('"', '&quot;');
			var style = "";
			style += "width: 90%";
			return '<textarea class="json-string" name="' + inputName + '" style="' + style + '">'
				+ valueHtml
				+ '</textarea>';
		},
		action: function (context, actionName, arg1) {
			if (actionName == 'new-value') {
				context.data.setValue(arg1);
			}
		},
		render: function (element, data, context) {
			//Use contentEditable
			if (element.contentEditable !== null) {
				element.innerHTML = '<div class="json-string json-string-content-editable">' + escapeHtml(data.value()).replace(/\n/g, "<br>") + '</div>';
				var valueSpan = element.childNodes[0];
				valueSpan.contentEditable = "true";
				valueSpan.onblur = function () {
					var newString = getText(valueSpan);
					data.setValue(newString);
				};
				return;
			}

			if (typeof window.getComputedStyle != "function") {
				return;
			}
			// min/max length
			var minLength = data.schemas().minLength();
			var maxLength = data.schemas().maxLength();
			var noticeBox = document.createElement("span");
			noticeBox.className="json-string-notice";
			function updateNoticeBox(stringValue) {
				if (stringValue.length < minLength) {
					noticeBox.innerHTML = 'Too short (minimum ' + minLength + ' characters)';
				} else if (maxLength != null && stringValue.length > maxLength) {
					noticeBox.innerHTML = 'Too long (+' + (stringValue.length - maxLength) + ' characters)';
				} else if (maxLength != null) {
					noticeBox.innerHTML = (maxLength - stringValue.length) + ' characters left';
				} else {
					noticeBox.innerHTML = "";
				}
			}

			// size match
			var sizeMatchBox = document.createElement("div");

			var textarea = null;
			for (var i = 0; i < element.childNodes.length; i++) {
				if (element.childNodes[i].nodeType == 1) {
					textarea = element.childNodes[i];
					break;
				}
			}
			element.insertBefore(sizeMatchBox, textarea);
			copyTextStyle(textarea, sizeMatchBox);
			sizeMatchBox.style.display = "inline";
			sizeMatchBox.style.position = "absolute";
			sizeMatchBox.style.width = "auto";
			sizeMatchBox.style.height = "auto";
			sizeMatchBox.style.left = "-100000px";
			sizeMatchBox.style.top = "0px";
			sizeMatchBox.style.whiteSpace = "pre";
			sizeMatchBox.style.zIndex = -10000;
			var suffix = "MMMMM";
			updateTextareaSize(textarea, sizeMatchBox, suffix);

			textarea.value = data.value();
			textarea.onkeyup = function () {
				updateNoticeBox(this.value);
				updateTextareaSize(this, sizeMatchBox, suffix);
			};
			textarea.onfocus = function () {
				updateNoticeBox(data.value());
				suffix = "MMMMM\nMMM";
				updateTextareaSize(this, sizeMatchBox, suffix);
			};
			textarea.onblur = function () {
				data.setValue(this.value);
				noticeBox.innerHTML = "";
				suffix = "MMMMM";
				updateTextareaSize(this, sizeMatchBox, suffix);
			};
			element.appendChild(noticeBox);
			textarea = null;
			element = null;
		},
		update: function (element, data, context, operation) {
			if (element.contentEditable !== null) {
				var valueSpan = element.childNodes[0];
				valueSpan.innerHTML = escapeHtml(data.value()).replace(/\n/g, "<br>");
				return false;
			};
			if (operation.action() == "replace") {
				var textarea = null;
				for (var i = 0; i < element.childNodes.length; i++) {
					if (element.childNodes[i].tagName.toLowerCase() == "textarea") {
						textarea = element.childNodes[i];
						break;
					}
				}
				textarea.value = data.value();
				textarea.onkeyup();
				return false;
			} else {
				return true;
			}
		},
		filter: function (data) {
			return data.basicType() == "string" && !data.readOnly();
		}
	});

	// Display/edit boolean
	Jsonary.render.register({
		render: function (element, data) {
			var valueSpan = document.createElement("a");
			if (data.value()) {
				valueSpan.setAttribute("class", "json-boolean-true");
				valueSpan.innerHTML = "yes";
			} else {
				valueSpan.setAttribute("class", "json-boolean-false");
				valueSpan.innerHTML = "no";
			}
			element.appendChild(valueSpan);
			if (!data.readOnly()) {
				valueSpan.setAttribute("href", "#");
				valueSpan.onclick = function (event) {
					data.setValue(!data.value());
					return false;
				};
			}
			valueSpan = null;
			element = null;
		},
		filter: function (data) {
			return data.basicType() == "boolean";
		}
	});

	// Edit number
	Jsonary.render.register({
		renderHtml: function (data, context) {
			var result = context.actionHtml('<span class="json-number">' + data.value() + '</span>', "input");

			var interval = data.schemas().numberInterval();
			if (interval != undefined) {
				var minimum = data.schemas().minimum();
				if (minimum == null || data.value() > minimum + interval || data.value() == (minimum + interval) && !data.schemas().exclusiveMinimum()) {
					result = context.actionHtml('<span class="json-number-decrement button">-</span>', 'decrement') + result;
				}

				var maximum = data.schemas().maximum();
				if (maximum == null || data.value() < maximum - interval || data.value() == (maximum - interval) && !data.schemas().exclusiveMaximum()) {
					result += context.actionHtml('<span class="json-number-increment button">+</span>', 'increment');
				}
			}
			return result;
		},
		action: function (context, actionName) {
			var data = context.data;
			var interval = data.schemas().numberInterval();
			if (actionName == "increment") {
				data.setValue(data.value() + interval);
			} else if (actionName == "decrement") {
				data.setValue(data.value() - interval);
			} else if (actionName == "input") {
				var newValueString = prompt("Enter number: ", data.value());
				var value = parseFloat(newValueString);
				if (!isNaN(value)) {
					if (interval != undefined) {
						value = Math.round(value/interval)*interval;
					}
					var valid = true;
					var minimum = data.schemas().minimum();
					if (minimum != undefined) {
						if (value < minimum || (value == minimum && data.schemas().exclusiveMinimum())) {
							valid = false;
						}
					}
					var maximum = data.schemas().maximum();
					if (maximum != undefined) {
						if (value > maximum || (value == maximum && data.schemas().exclusiveMaximum())) {
							valid = false;
						}
					}
					if (!valid) {
						value = data.schemas().createValueNumber();
					}
					data.setValue(value);
				}
			}
		},
		filter: function (data) {
			return (data.basicType() == "number" || data.basicType() == "integer") && !data.readOnly();
		}
	});

	// Edit enums
	Jsonary.render.register({
		render: function (element, data, context) {
			var enumValues = data.schemas().enumValues();
			if (enumValues.length == 0) {
				element.innerHTML = '<span class="json-enum-invalid">invalid</span>';
				return;
			} else if (enumValues.length == 1) {
				if (typeof enumValues[0] == "string") {
					element.innerHTML = '<span class="json-string">' + escapeHtml(enumValues[0]) + '</span>';
				} else if (typeof enumValues[0] == "number") {
					element.innerHTML = '<span class="json-number">' + enumValues[0] + '</span>';
				} else if (typeof enumValues[0] == "boolean") {
					var text = (enumValues[0] ? "yes" : "no");
					element.innerHTML = '<span class="json-boolean-' + text + '">' + text + '</span>';
				} else {
					element.innerHTML = '<span class="json-raw">' + escapeHtml(JSON.stringify(enumValues[0])) + '</span>';
				}
				return;
			}
			var select = document.createElement("select");
			for (var i = 0; i < enumValues.length; i++) {
				var option = document.createElement("option");
				option.setAttribute("value", i);
				if (data.equals(Jsonary.create(enumValues[i]))) {
					option.selected = true;
				}
				option.appendChild(document.createTextNode(enumValues[i]));
				select.appendChild(option);
			}
			select.onchange = function () {
				var index = this.value;
				data.setValue(enumValues[index]);
			}
			element.appendChild(select);
			element = select = option = null;
		},
		filter: function (data) {
			return !data.readOnly() && data.schemas().enumValues() != null;
		}
	});

})();
