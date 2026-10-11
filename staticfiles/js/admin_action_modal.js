(function () {
    function initialize(modal) {
        if (modal.getAttribute('data-initialized')) return;
        modal.setAttribute('data-initialized', 'true');
        document.body.appendChild(modal);
        var action = modal.getAttribute('data-action');
        var inputName = modal.getAttribute('data-input-name');
        var input = modal.querySelector('textarea');
        var error = modal.querySelector('[data-modal-error]');
        var confirm = modal.querySelector('[data-modal-confirm]');
        var cancel = modal.querySelector('[data-modal-cancel]');
        var activeForm = null;
        var activeUrl = null;
        var previousFocus = null;
        var previousOverflow = '';
        var submitting = false;

        function show() {
            previousFocus = document.activeElement;
            previousOverflow = document.body.style.overflow;
            document.body.style.overflow = 'hidden';
            modal.classList.remove('hidden');
            input.value = '';
            input.removeAttribute('aria-invalid');
            error.classList.add('hidden');
            input.focus();
        }
        function close() {
            if (submitting) return;
            modal.classList.add('hidden');
            document.body.style.overflow = previousOverflow;
            activeForm = null;
            activeUrl = null;
            if (previousFocus) previousFocus.focus();
        }
        function hidden(form, name, value) {
            var field = document.createElement('input');
            field.type = 'hidden';
            field.name = name;
            field.value = value;
            form.appendChild(field);
        }
        document.addEventListener('submit', function (event) {
            var form = event.target;
            var selected = form.querySelector('select[name="action"]');
            if (!selected || selected.value !== action) return;
            if (form.querySelector('input[name="_selected_action"]') &&
                !form.querySelector('input[name="_selected_action"]:checked')) return;
            event.preventDefault();
            activeForm = form;
            activeUrl = null;
            show();
        });
        document.addEventListener('click', function (event) {
            var link = event.target.closest('a');
            var href = link && link.getAttribute('href');
            if (!href || href.split('?')[0].indexOf('/' + action + '/') === -1) return;
            event.preventDefault();
            activeForm = null;
            activeUrl = link.href;
            show();
        });
        cancel.addEventListener('click', close);
        modal.querySelector('[data-modal-backdrop]').addEventListener('click', close);
        modal.querySelector('[data-modal-layout]').addEventListener('click', function (event) {
            if (event.target === this) close();
        });
        modal.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') { event.preventDefault(); close(); }
            if (event.key === 'Tab') {
                if (event.shiftKey && document.activeElement === input) {
                    event.preventDefault(); confirm.focus();
                } else if (!event.shiftKey && document.activeElement === confirm) {
                    event.preventDefault(); input.focus();
                }
            }
        });
        confirm.addEventListener('click', function () {
            if (submitting) return;
            var value = input.value.replace(/^\s+|\s+$/g, '');
            if (!value) {
                error.classList.remove('hidden');
                input.setAttribute('aria-invalid', 'true');
                input.focus();
                return;
            }
            var form = activeForm;
            if (!form && activeUrl) {
                form = document.createElement('form');
                form.method = 'POST';
                form.action = activeUrl;
                var csrf = document.querySelector('[name="csrfmiddlewaretoken"]');
                if (csrf) hidden(form, 'csrfmiddlewaretoken', csrf.value);
                document.body.appendChild(form);
            }
            if (!form) return;
            hidden(form, inputName, value);
            if (activeForm) {
                var selects = form.querySelectorAll('select[name="action"]');
                for (var j = 0; j < selects.length; j++) selects[j].value = action;
            }
            submitting = true;
            confirm.disabled = true;
            HTMLFormElement.prototype.submit.call(form);
        });
    }
    function start() {
        var modals = document.querySelectorAll('[data-action-modal]');
        for (var i = 0; i < modals.length; i++) initialize(modals[i]);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
}());
