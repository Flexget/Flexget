(function (Jsonary) {
	Jsonary.render.register({
		renderHtml: function (data, context) {
			var result = '<div class="function-definition">';
			if (!context.uiState.expanded) {
				result += context.actionHtml('<span class="expand">show</span>', 'expand');
			} else {
				result += context.actionHtml('<span class="expand">hide</span>', 'collapse');
			}
			result += '<div class="function-definition-signature">';
			result += '<span class="function-keyword">function</span> ';
			var title = "";
			if (data.parent() != null && data.parent().basicType() == "object") {
				title = data.parentKey();
			}
			result += '<span class="function-name">' + title + '</span>';
			result += '(';
			data.property("arguments").items(function (index, subData) {	
				if (index > 0) {
					result += ', ';
				}
				var title = subData.propertyValue("title") || ("arg" + index);
				result += '<span class="function-argument-name">' + title + '</span>';
			});
			result += ')';
			result += '</div>';
			
			if (context.uiState.expanded) {
				result += '<div class="function-definition-section">';
				result += context.renderHtml(data.property("description"));
				result += '</div>';
			
				result += '<h2 class="function-definition-section-title">Arguments:</h2>';
				result += '<div class="function-definition-section">';
				result += context.renderHtml(data.property("arguments"));
				result += '</div>';

				result += '<h2 class="function-definition-section-title">Return value:</h2>';
				result += '<div class="function-definition-section">';
				result += context.renderHtml(data.property("return"));
				if (data.readOnly() && !data.property("return").defined()) {
					result += 'undefined';
				}
				result += '</div>';
			}
			return result + '</div>';
		},
		action: function (context, actionName, tabKey) {
			if (actionName == "expand") {
				context.uiState.expanded = true;
			} else {
				context.uiState.expanded = false;
			}
			return true;
		},
		filter: function (data, schemas) {
			return schemas.containsUrl('api-schema.json#/functionDefinition');
		},
		update: function (element, data, context, operation) {
			if (operation.hasPrefix(data.property("arguments")) && operation.depthFrom(data.property("arguments")) <= 2) {
				return true;
			}
			return this.defaultUpdate(element, data, context, operation);
		}
	});
})(Jsonary);
