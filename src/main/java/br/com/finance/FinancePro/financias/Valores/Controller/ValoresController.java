package br.com.finance.FinancePro.financias.Valores.Controller;

import br.com.finance.FinancePro.financias.Valores.Model.ValoresModel;
import br.com.finance.FinancePro.financias.Valores.Service.ValoresService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/transações")
public class ValoresController {

    private final ValoresService valoresService;

    public ValoresController(ValoresService valoresService) {this.valoresService = valoresService;}

    @GetMapping
    public List<ValoresModel> getAll() {return valoresService.getAll();}

    @PostMapping
    public ValoresModel create(@RequestBody ValoresModel transacao) {return valoresService.save(transacao);}

    @DeleteMapping("/{id}")
    public void delete(@PathVariable long id) {
        valoresService.delete(id);}
}
