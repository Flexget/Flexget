(function (Jsonary) {

	Jsonary.render.Components.add("LIST_SCHEMAS");

	Jsonary.render.register({
		component: Jsonary.render.Components.LIST_SCHEMAS,
		update: function (element, data, context, operation) {
			// We don't care about data changes - when the schemas change, a re-render is forced anyway.
			return false;
		},
		renderHtml: function (data, context) {
			var result = "";
			data.schemas().each(function (index, schema) {
				if (schema.title() == null) {
					return;
				}
				var html = '<span class="button">' + Jsonary.escapeHtml(schema.title()) + '</span>';
				result += context.actionHtml(html, 'view-schema', index);
			});
			if (context.uiState.viewSchema != undefined) {
				var schema = data.schemas()[context.uiState.viewSchema];
				result += '<div class="prompt-outer"><div class="prompt-inner">';
				result += context.actionHtml('<div class="prompt-overlay"></div>', 'hide-schema');
				result += '<div class="prompt-box"><h1>' + Jsonary.escapeHtml(schema.title()) + '</h1><h2>' + schema.referenceUrl() + '</h2><pre>'
					+ Jsonary.escapeHtml(JSON.stringify(schema.data.value(), null, 4))
					+ '</pre></div>';
				result += '</div></div>';
			}
			result += context.renderHtml(data);
			return result;
		},
		action: function (context, actionName, arg1) {
			if (actionName == "view-schema") {
				context.uiState.viewSchema = arg1;
				return true;
			} else {
				delete context.uiState.viewSchema;
				return true;
			}
		},
		filter: function () {
			return true;
		}
	});
})(Jsonary);
