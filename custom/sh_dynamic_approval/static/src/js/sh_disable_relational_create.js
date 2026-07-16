import { patch } from "@web/core/utils/patch";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

patch(Many2XAutocomplete.prototype, {
    get activeActions() {
        const activeActions = super.activeActions;
        const activeModel = this.env.model?.root?.resModel || this.env.searchModel?.resModel;
        
        if (activeModel && activeModel.startsWith('sh.approval.')) {
            return {
                ...activeActions,
                create: false,
                createEdit: false,
            };
        }
        
        return activeActions;
    },

    addCreateSuggestion() {
        const activeModel = this.env.model?.root?.resModel || this.env.searchModel?.resModel;
        if (activeModel && activeModel.startsWith('sh.approval.')) {
            return false;
        }
        return super.addCreateSuggestion(...arguments);
    },

    addCreateEditSuggestion() {
        const activeModel = this.env.model?.root?.resModel || this.env.searchModel?.resModel;
        if (activeModel && activeModel.startsWith('sh.approval.')) {
            return false;
        }
        return super.addCreateEditSuggestion(...arguments);
    },

    addSearchMoreSuggestion({ records, request }) {
        return request.length > 0 || super.addSearchMoreSuggestion({ records, request });
    },
});
