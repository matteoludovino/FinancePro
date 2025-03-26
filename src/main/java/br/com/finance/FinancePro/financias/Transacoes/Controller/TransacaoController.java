package br.com.finance.FinancePro.financias.Transacoes.Controller;

import br.com.finance.FinancePro.financias.Transacoes.Model.TransacaoModel;
import br.com.finance.FinancePro.financias.Transacoes.Service.TransacaoService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/transações")
public class TransacaoController {

    private final TransacaoService transacaoService;

    public TransacaoController(TransacaoService transacaoService) {this.transacaoService = transacaoService;}

    @GetMapping
    public List<TransacaoModel> getAll() {return transacaoService.getAll();}

    @PostMapping
    public TransacaoModel create(@RequestBody TransacaoModel transacao) {return transacaoService.save(transacao);}

    @DeleteMapping("/{id}")
    public void delete(@PathVariable long id) {
        transacaoService.delete(id);}
}
